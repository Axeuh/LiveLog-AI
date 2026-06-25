"""
统一数据检查工具 - 输出按时间混排的完整数据时间线，去重显示变化点
自动解析GPS坐标→地名（百度逆地理编码，限2并发/1秒最多2次/缓存去重）
用法:
    python analysis/data_check.py 2026-06-13 --hours 12:00~14:00
"""

import json, sys, os, requests, time

# 百度逆地理编码
BAIDU_AK = '(占位符)'
GEO_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'gps_cache.json')
CONCURRENCY_LIMIT = 2
BATCH_DELAY = 0.5

# 加载GPS缓存
_geo_cache = {}
if os.path.exists(GEO_CACHE_FILE):
    try:
        with open(GEO_CACHE_FILE, 'r', encoding='utf-8') as f:
            _geo_cache = json.load(f)
    except:
        _geo_cache = {}

def reverse_geocode(gps_str):
    """解析GPS坐标，返回地名，带缓存"""
    if gps_str in _geo_cache:
        return _geo_cache[gps_str]
    
    parts = gps_str.split(',')
    if len(parts) != 2:
        return gps_str
    
    lat, lng = parts[0].strip(), parts[1].strip()
    url = f'https://api.map.baidu.com/reverse_geocoding/v3/?ak={BAIDU_AK}&output=json&coordtype=wgs84ll&location={lat},{lng}'
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('status') == 0:
            result = data.get('result', {})
            addr = result.get('formatted_address', '')
            poi = result.get('pois', [])
            poi_names = [p.get('name', '') for p in poi[:3]]
            business = result.get('business', '')
            
            location = f'{addr}'
            if poi_names:
                location += f' | 附近: {", ".join(poi_names)}'
            _geo_cache[gps_str] = location
        else:
            _geo_cache[gps_str] = gps_str
    except:
        _geo_cache[gps_str] = gps_str
    
    time.sleep(0.5)  # 1秒最多2次，避免百度API限流
    return _geo_cache[gps_str]

def save_geo_cache():
    """保存GPS缓存"""
    try:
        os.makedirs(os.path.dirname(GEO_CACHE_FILE), exist_ok=True)
        with open(GEO_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_geo_cache, f, ensure_ascii=False, indent=2)
    except:
        pass

def load_events(date_str):
    for base in [os.path.dirname(os.path.abspath(__file__)) + '/..', os.getcwd()]:
        path = os.path.join(base, 'data', date_str, 'perception.jsonl')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return [json.loads(l) for l in f if l.strip()]
    print(f'文件不存在: data/{date_str}/perception.jsonl', file=sys.stderr)
    return None

def filter_events(events, time_range=None):
    if not time_range: return events
    start_t, end_t = time_range.split('~')
    result = []
    for e in events:
        t = e.get('t', '')
        if start_t <= end_t:
            if start_t <= t <= end_t: result.append(e)
        else:
            if t >= start_t or t <= end_t: result.append(e)
    return result

def build_timeline(events):
    """构建统一时间线，所有类型按时间混排，去重"""
    timeline = []
    
    # 辅助：去重跟踪
    last_gps = None
    last_hr = None
    last_steps = None
    last_wifi = None
    last_screen = None
    
    for e in sorted(events, key=lambda x: x.get('t','')):
        t = e.get('t', '')
        tp = e.get('type', '')
        
        if tp == 'voice':
            for s in e.get('segments', []):
                text = s.get('text', '').strip()
                if text and 'nospeech' not in text and 'Event_UNK' not in text:
                    sim = s.get('voiceprint_sim') or 0
                    tag = '[环境]' if sim < 0.3 else '[混合]' if sim < 0.5 else '[用户]' if sim < 0.7 else '[确定]'
                    emo = s.get('emotion_tag', '')
                    extra = f' emo={emo}' if emo else ''
                    timeline.append((t, '语音', f'sim={sim:.2f} {tag} "{text[:120]}"{extra}'))
        
        elif tp == 'sensor':
            gps = e.get('gps')
            if gps and gps != last_gps:
                location = reverse_geocode(gps)
                timeline.append((t, 'GPS', f'{gps} → {location}'))
                last_gps = gps
            
            hr = e.get('hr', 0)
            steps = e.get('steps', 0)
            if hr and hr != last_hr:
                extra = ''
                if e.get('stress'): extra += f' stress={e["stress"]}'
                if e.get('spo2'): extra += f' spo2={e["spo2"]}'
                timeline.append((t, '心率', f'HR={hr} steps={steps}{extra}'))
                last_hr = hr
            if steps != last_steps:
                timeline.append((t, '步数', str(steps)))
                last_steps = steps
        
        elif tp == 'screen':
            status = '解锁' if e.get('locked') == False else '锁屏'
            if status != last_screen:
                timeline.append((t, '屏幕', status))
                last_screen = status
        
        elif tp == 'app':
            app_name = e.get('app', '')
            if app_name:
                timeline.append((t, 'App', app_name))
        
        elif tp == 'media':
            title = e.get('media_title', '')
            artist = e.get('media_artist', '')
            app = e.get('media_app', '')
            state = e.get('media_state', '')
            if title:
                timeline.append((t, '音乐', f'"{title}" - {artist} ({app}) [{state}]'))
        
        elif tp == 'notify':
            pkg = e.get('pkg') or ''
            text = e.get('text', '')
            if text:
                timeline.append((t, '通知', f'{pkg}: {text[:80]}'))
        
        elif tp == 'input':
            text = e.get('text', '')
            if text:
                timeline.append((t, '输入', text[:80]))
        
        elif tp == 'device_env':
            wifi = e.get('wifi', {})
            conn = wifi.get('connected')
            if conn is not None and conn != last_wifi:
                status = 'WiFi连' if conn else 'WiFi断'
                rssi = wifi.get('rssi', '')
                timeline.append((t, '网络', f'{status} rssi={rssi}'))
                last_wifi = conn
    
    # 按时间排序
    timeline.sort(key=lambda x: x[0])
    return timeline

def print_stats(events):
    """输出统计摘要"""
    types_count = {}
    for e in events:
        tp = e.get('type', '?')
        types_count[tp] = types_count.get(tp, 0) + 1
    
    # 语音统计
    voice_events = [e for e in events if e.get('type') == 'voice']
    segments = []
    for v in voice_events:
        for s in v.get('segments', []):
            text = s.get('text', '').strip()
            if text and 'nospeech' not in text:
                segments.append(s)
    
    print(f'总事件: {len(events)}条 | 类型: {dict(sorted(types_count.items()))}')
    if segments:
        lt03 = sum(1 for s in segments if (s.get('voiceprint_sim') or 0) < 0.3)
        bt03 = sum(1 for s in segments if 0.3 <= (s.get('voiceprint_sim') or 0) < 0.5)
        bt05 = sum(1 for s in segments if 0.5 <= (s.get('voiceprint_sim') or 0) < 0.7)
        gt07 = sum(1 for s in segments if (s.get('voiceprint_sim') or 0) >= 0.7)
        print(f'语音: {len(voice_events)}事件 {len(segments)}段 | 声纹: 环境{lt03} 混合{bt03} 用户{bt05} 确定{gt07}')

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    date_str = sys.argv[1]
    events = load_events(date_str)
    if not events: sys.exit(1)
    
    time_range = None
    for i, arg in enumerate(sys.argv):
        if arg == '--hours' and i+1 < len(sys.argv):
            time_range = sys.argv[i+1]
    
    filtered = filter_events(events, time_range)
    
    print(f'\n数据检查: {date_str}', end='')
    if time_range: print(f' [{time_range}]', end='')
    print()
    
    print_stats(filtered)
    
    # 输出统一时间线
    timeline = build_timeline(filtered)
    if timeline:
        print(f'\n时间线 ({len(timeline)}条变化):')
        print('─' * 60)
        for time, label, detail in timeline:
            print(f'  {time} [{label}] {detail}')
    else:
        print('\n(该时段无数据变化)')

if __name__ == '__main__':
    main()
    save_geo_cache()
