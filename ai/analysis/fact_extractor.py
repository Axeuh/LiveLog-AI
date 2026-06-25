#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
事实提取器 - 将原始perception.jsonl转换为可读的Markdown格式

去机器冗余但保留全量语音信息。
- GPS不变不重复
- HR取范围值
- VAD重复文本去重（前40字相同视为重复）
- 全量保留语音原文（不折叠不裁剪）

用法:
    python ai/analysis/fact_extractor.py 2026-06-14
    python ai/analysis/fact_extractor.py 2026-06-14 --hours 06:00~14:00
    python ai/analysis/fact_extractor.py 2026-06-14 --output /path/to/output.md
"""

import json
import sys
import os
import requests
import time
from datetime import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 百度逆地理编码配置
BAIDU_AK = '(占位符)'
GEO_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'gps_cache.json'
)

# GPS缓存
_geo_cache = {}
if os.path.exists(GEO_CACHE_FILE):
    try:
        with open(GEO_CACHE_FILE, 'r', encoding='utf-8') as f:
            _geo_cache = json.load(f)
    except Exception:
        _geo_cache = {}


def reverse_geocode(gps_str):
    """解析GPS坐标，返回地名（带缓存）"""
    if gps_str in _geo_cache:
        return _geo_cache[gps_str]

    parts = gps_str.split(',')
    if len(parts) != 2:
        _geo_cache[gps_str] = gps_str
        return gps_str

    lat, lng = parts[0].strip(), parts[1].strip()
    url = (
        f'https://api.map.baidu.com/reverse_geocoding/v3/'
        f'?ak={BAIDU_AK}&output=json&coordtype=wgs84ll&location={lat},{lng}'
    )

    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('status') == 0:
            result = data.get('result', {})
            addr = result.get('formatted_address', '')
            poi = result.get('pois', [])
            poi_names = [p.get('name', '') for p in poi[:3]]
            location = addr
            if poi_names:
                location += ' | 附近: ' + ', '.join(poi_names)
            _geo_cache[gps_str] = location
        else:
            _geo_cache[gps_str] = gps_str
    except Exception:
        _geo_cache[gps_str] = gps_str

    time.sleep(0.5)  # 1秒最多2次，避免百度API限流
    return _geo_cache[gps_str]


def save_geo_cache():
    """保存GPS缓存"""
    try:
        os.makedirs(os.path.dirname(GEO_CACHE_FILE), exist_ok=True)
        with open(GEO_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_geo_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _find_data_file(date_str, filename):
    """在多个可能路径中查找数据文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()
    search_paths = [
        os.path.join(cwd, 'ai', 'data', date_str, filename),
        os.path.join(cwd, 'data', date_str, filename),
        os.path.join(script_dir, '..', 'data', date_str, filename),
    ]
    for p in search_paths:
        if os.path.exists(p):
            return p
    return None


def load_perception(date_str):
    """加载指定日期的perception.jsonl"""
    path = _find_data_file(date_str, 'perception.jsonl')
    if not path:
        print(f'错误: 未找到 data/{date_str}/perception.jsonl', file=sys.stderr)
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return [json.loads(l) for l in f if l.strip()]


def load_health(date_str):
    """加载指定日期的health.json"""
    path = _find_data_file(date_str, 'health.json')
    if not path:
        return {'samples': [], 'sleep_data': {}}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def clean_time_str(t_str):
    """统一时间格式：去除日期前缀和时区后缀，返回 HH:MM:SS"""
    if not t_str:
        return ''
    clean = t_str
    if 'T' in clean:
        clean = clean.split('T')[1]
    if '+' in clean and clean.count(':') >= 2:
        clean = clean.split('+')[0]
    clean = clean.rstrip('Z')
    return clean


def get_slot_key(t_str):
    """将时间戳转为5分钟时段键 'HH:MM'"""
    clean = clean_time_str(t_str)
    if not clean:
        return '00:00'
    parts = clean.split(':')
    h = int(parts[0])
    m = int(parts[1])
    slot_m = (m // 5) * 5
    return f'{h:02d}:{slot_m:02d}'


def seconds_since_midnight(t_str):
    """将时间戳转为秒数"""
    clean = clean_time_str(t_str)
    if not clean:
        return 0
    parts = clean.split(':')
    h = int(parts[0])
    m = int(parts[1])
    s = int(parts[2]) if len(parts) > 2 else 0
    return h * 3600 + m * 60 + s


def secs_to_str(secs):
    """秒数转为 HH:MM:SS 字符串"""
    total = int(secs) % 86400
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f'{h:02d}:{m:02d}:{s:02d}'


def is_valid_voice_text(text):
    """判断语音文本是否有效（非空、非nospeech/Event_UNK）"""
    if not text or not text.strip():
        return False
    stripped = text.strip()
    if '<|nospeech|>' in stripped or '<|Event_UNK|>' in stripped:
        return False
    return True


def get_voice_dedup_key(text):
    """语音去重键：前40字"""
    return text.strip()[:40]


def format_sim_tag(sim):
    """根据声纹相似度返回标注标签"""
    if sim >= 0.7:
        return '确定'
    elif sim >= 0.5:
        return '用户'
    elif sim >= 0.3:
        return '混合'
    else:
        return '环境/他人'


def parse_time_to_minutes(t_str):
    """将多种时间格式解析为当天分钟数(0~1440)"""
    if not t_str:
        return None
    clean = t_str
    # 去掉日期部分 (如 "2026-06-22T19:13:50+08:00" -> "19:13:50+08:00")
    if 'T' in clean:
        clean = clean.split('T')[1]
    # 去掉时区偏移 (如 "19:13:50+08:00" -> "19:13:50")
    if '+' in clean and clean.count(':') >= 2:
        clean = clean.split('+')[0]
    # 去掉可能的Z后缀
    clean = clean.rstrip('Z')
    parts = clean.split(':')
    if len(parts) >= 2:
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except ValueError:
            return None
    return None


def filter_events_by_time(events, time_range_str):
    """按时间范围过滤事件"""
    if not time_range_str:
        return events
    # 格式: "06:00~14:00"
    start_str, end_str = time_range_str.split('~')
    start_min = int(start_str[:2]) * 60 + int(start_str[3:5])
    end_min = int(end_str[:2]) * 60 + int(end_str[3:5])

    result = []
    for e in events:
        t = e.get('t', '')
        t_min = parse_time_to_minutes(t)
        if t_min is None:
            continue

        if start_min <= end_min:
            if start_min <= t_min <= end_min:
                result.append(e)
        else:
            # 跨天 (如 22:00~06:00)
            if t_min >= start_min or t_min <= end_min:
                result.append(e)
    return result


def group_by_slot(events):
    """将事件按5分钟时段分组，返回有序列表 [(slot_key, [events])]"""
    slot_map = {}
    for e in events:
        t = e.get('t', '')
        if not t:
            continue
        slot = get_slot_key(t)
        if slot not in slot_map:
            slot_map[slot] = []
        slot_map[slot].append(e)

    result = []
    for sk in sorted(slot_map.keys()):
        result.append((sk, slot_map[sk]))
    return result


# pyright: reportOptionalMemberAccess=false, reportAttributeAccessIssue=false


def collect_slot_data(events, prev_state):
    """收集一个时段内所有类型的数据，返回摘要字典"""
    data = {
        'gps': prev_state.get('gps'),
        'gps_time': None,
        'gps_location': prev_state.get('gps_location'),
        'hr_values': [],
        'steps': None,
        'battery': None,
        'phone_battery': None,
        'screen_locked': prev_state.get('screen_locked'),
        'screen_times': [],
        'voice_timeline': [],  # 统一时间线：语音段 + 环境音事件，按时间排列
        'apps': [],
        'medias': [],
        'notifies': [],
        'inputs': [],
        'web_messages': [],
        'task_triggers': [],
        'wifi_connected': prev_state.get('wifi_connected'),
        'wifi_rssi': None,
        'pc_windows': [],
        'pc_idle': prev_state.get('pc_idle'),
        'pc_idle_seconds': prev_state.get('pc_idle_seconds'),
        'pc_idle': None,           # PC待机状态
        'pc_idle_seconds': None,   # 待机秒数
        'seen_voice_texts': set(),
    }

    for e in events:
        t = e.get('t', '')
        tp = e.get('type', '')

        if tp == 'sensor':
            gps = e.get('gps')
            if gps and gps != data['gps']:
                data['gps'] = gps
                data['gps_time'] = t[:5]
                data['gps_location'] = reverse_geocode(gps)

            hr = e.get('hr')
            if hr:
                data['hr_values'].append((t[:5], hr))

            steps = e.get('steps')
            if steps is not None:
                data['steps'] = steps
            battery = e.get('battery')
            if battery is not None:
                data['battery'] = battery
            pb = e.get('phone_battery')
            if pb is not None:
                data['phone_battery'] = pb

        elif tp == 'screen':
            locked = e.get('locked')
            if locked is not None:
                data['screen_locked'] = locked
                data['screen_times'].append((t[:5], '锁屏' if locked else '解锁'))

        elif tp == 'voice':
            event_sec = seconds_since_midnight(t)
            segs = e.get('segments', [])
            # 收集语音段
            items = []
            for s in segs:
                text = s.get('text', '').strip()
                sim = s.get('voiceprint_sim') or 0
                vp_stats = s.get('voiceprint_stats', None)
                speech_prob = s.get('speech_prob', None)
                silence_ratio = s.get('silence_ratio', None)
                offset = s.get('start', 0)  # 兼容旧格式：无 start 时用 0
                if is_valid_voice_text(text):
                    dedup_key = get_voice_dedup_key(text)
                    if dedup_key not in data['seen_voice_texts']:
                        data['seen_voice_texts'].add(dedup_key)
                        items.append({
                            'type': 'speech',
                            'offset': offset,
                            'sim': sim,
                            'emotion': s.get('emotion_tag', ''),
                            'text': text,
                            'speaker': s.get('voiceprint_speaker', ''),
                            'vp_windows': s.get('voiceprint_windows', None),
                            'vp_stats': vp_stats,
                            'speech_prob': speech_prob,
                            'silence_ratio': silence_ratio,
                        })
            # 收集音频事件（与语音段时间线合并）
            for ae in e.get('audio_events', []):
                label = ae.get('label_cn', ae.get('label', ''))
                prob = ae.get('probability', 0)
                offset = ae.get('start', 0)  # 兼容旧格式
                if prob >= 0.1 and label:
                    items.append({
                        'type': 'audio_event',
                        'offset': offset,
                        'label': label,
                        'probability': prob,
                    })
            # 按 (事件时间, 偏移量) 排序后追加
            for item in sorted(items, key=lambda x: (event_sec, x['offset'])):
                item['event_time'] = event_sec
                item['time_display'] = t[:5]
                data['voice_timeline'].append(item)

        elif tp == 'app':
            app_name = e.get('app', '')
            if app_name:
                data['apps'].append((t[:5], app_name))

        elif tp == 'media':
            title = e.get('media_title', '')
            artist = e.get('media_artist', '')
            state = e.get('media_state', '')
            if title:
                data['medias'].append((t[:5], title, artist, state))

        elif tp == 'notify':
            # 兼容新旧格式：app(新) > pkg(旧)
            app = e.get('app', e.get('pkg', ''))
            title = e.get('title', '')
            text = e.get('text', '')
            items = e.get('items', [])
            if items:
                for item in items:
                    itext = item.get('text', '')
                    iapp = item.get('app', item.get('pkg', ''))
                    ititle = item.get('title', '')
                    if itext:
                        data['notifies'].append((t[:5], iapp, ititle, itext))
            elif text:
                data['notifies'].append((t[:5], app, title, text))

        elif tp == 'input':
            text = e.get('text', '')
            if text:
                data['inputs'].append((t[:5], text))

        elif tp == 'web_message':
            content = e.get('content', '')
            source = e.get('source', 'web_message')
            if content:
                if source == 'task_trigger':
                    data['task_triggers'].append((t[:5], content))
                else:
                    data['web_messages'].append((t[:5], content))

        elif tp == 'device_env':
            wifi = e.get('wifi', {})
            conn = wifi.get('connected')
            if conn is not None:
                data['wifi_connected'] = conn
                data['wifi_rssi'] = wifi.get('rssi')

        elif tp == 'pc_idle':
            payload = e.get('payload', {})
            state = payload.get('state', '')
            idle = payload.get('idle_seconds')
            if state:
                data['pc_idle'] = state
                data['pc_idle_seconds'] = idle

        elif tp == 'pc_window':
            payload = e.get('payload', {})
            proc = payload.get('process', '')
            title = payload.get('title', '')
            if proc:
                data['pc_windows'].append((t[:5], proc, title))

    return data


def is_quiet_slot(data):
    """判断一个时段是否是安静时段（无语音时间线/无GPS变化/无app使用）"""
    if len(data['voice_timeline']) > 0:
        return False
    if len(data['apps']) > 0:
        return False
    if len(data['medias']) > 0:
        return False
    if data['gps_time'] is not None:
        return False  # GPS变化了，说明在移动
    return True


def format_hr_trend(hr_values):
    """格式化HR趋势：全相同→单值; 有变化→首尾趋势"""
    if not hr_values:
        return ''
    vals = [v for _, v in hr_values]
    if len(set(vals)) == 1:
        return str(vals[0])
    # 只显示首尾变化点
    first = hr_values[0]
    last = hr_values[-1]
    return f'{first[1]}({first[0]})->{last[1]}({last[0]})'


def format_hr_range(hr_values):
    """格式化HR范围（用于合并时段）：返回 min~max"""
    if not hr_values:
        return ''
    vals = [v for _, v in hr_values]
    return f'{min(vals)}~{max(vals)}'


def get_health_hr_at_time(health_samples, target_time_str):
    """从health.json获取指定时间附近的HR值"""
    target_sec = seconds_since_midnight(target_time_str)
    best = None
    best_diff = 99999
    for s in health_samples:
        t_iso = s.get('t_iso', '')
        hr = s.get('hr')
        if hr and t_iso:
            try:
                dt = datetime.fromisoformat(t_iso)
                sample_sec = dt.hour * 3600 + dt.minute * 60 + dt.second
                diff = abs(sample_sec - target_sec)
                if diff < best_diff and diff < 180:
                    best = (dt.strftime('%H:%M'), hr)
                    best_diff = diff
            except Exception:
                pass
    return best


def format_slot_end(slot_key):
    """从时段键计算结束时间显示 (slot_key + 5分钟)"""
    h = int(slot_key[:2])
    m = int(slot_key[3:5]) + 5
    if m >= 60:
        h += 1
        m -= 60
    return f'{h:02d}:{m:02d}'


def build_section_markdown(slot_start, slot_end, data, health_samples=None, is_merged=False, hr_snap_str='', sleep_data=None, date_str=''):
    """构建单个时段的Markdown文本"""
    lines = []

    if is_merged:
        lines.append(f'## {slot_start}~{slot_end} -- 睡眠（合并时段，HR快照附后）')
    else:
        lines.append(f'## {slot_start}~{slot_end}')

    # 位置
    if data['gps'] and data['gps_location']:
        lines.append(f'\n- **位置**: {data["gps_location"]} `[GPS: {data["gps"]}]`')
    elif data['gps']:
        lines.append(f'\n- **位置**: `[GPS: {data["gps"]}]`')

    # 生理
    physio_parts = []
    # 优先使用感知数据中的HR，其次从health.json获取
    if data['hr_values']:
        if is_merged:
            hr_str = format_hr_range(data['hr_values'])
        else:
            hr_str = format_hr_trend(data['hr_values'])
        physio_parts.append(f'HR={hr_str}')
    if data['battery'] is not None:
        physio_parts.append(f'手环{data["battery"]}%')
    if data['phone_battery'] is not None:
        physio_parts.append(f'手机{data["phone_battery"]}%')
    if physio_parts:
        lines.append(f'- **生理**: {" | ".join(physio_parts)}')

    # 屏幕时间线（每次屏幕状态变化）
    if data['screen_times']:
        lines.append('- **屏幕时间线**:')
        for t, action in data['screen_times']:
            lines.append(f'  - {t}:00 {action}')
    elif data['screen_locked'] is not None:
        status = '锁屏' if data['screen_locked'] else '解锁'
        lines.append(f'- **屏幕**: {status}')

    # 语音时间线（语音段 + 环境音事件，按时间排列）
    if data['voice_timeline']:
        lines.append('- **语音时间线**:')
        # 环境音去重：同一时段内同标签只保留最高概率，最多显示5个
        audio_dedup = {}
        speech_items = []
        for item in data['voice_timeline']:
            if item['type'] == 'speech':
                speech_items.append(item)
            else:
                lbl = item['label']
                p = item['probability']
                if lbl not in audio_dedup or p > audio_dedup[lbl][0]:
                    audio_dedup[lbl] = (p, item)
        # 按时间渲染语音段 + top-5 环境音
        top_audio = sorted(audio_dedup.values(), key=lambda x: -x[0])[:5]
        top_audio_items = {id(v): True for _, v in top_audio}
        for item in data['voice_timeline']:
            if item['type'] == 'speech':
                emo_str = f' {item["emotion"]}' if item['emotion'] else ''
                speaker_str = f' [{item["speaker"]}]' if item.get('speaker') else ''
                # 时间信息：滑窗起止转为绝对时间戳
                vp_windows = item.get('vp_windows')
                if vp_windows and len(vp_windows) > 1:
                    event_sec = item.get('event_time', 0)
                    start_ms = vp_windows[0].get('start_ms', 0) if isinstance(vp_windows[0], dict) else 0
                    end_ms = vp_windows[-1].get('start_ms', 0) if isinstance(vp_windows[-1], dict) else 0
                    start_ts = secs_to_str(event_sec + start_ms / 1000.0)
                    end_ts = secs_to_str(event_sec + end_ms / 1000.0)
                    time_info = f' ({start_ts}~{end_ts})'
                else:
                    event_sec = item.get('event_time', 0)
                    offset = item.get('offset', 0)
                    time_info = f' ({secs_to_str(event_sec + offset)})'

                stats_str = ''
                if vp_windows and len(vp_windows) > 1:
                    scores = [w['score'] if isinstance(w, dict) else w for w in vp_windows[:8]]
                    w_vals = [f'{s:.2f}' for s in scores]
                    stats_str = f' 窗值: {"→".join(w_vals)}'
                lines.append(f'  - sim={item["sim"]:.2f}{time_info}{emo_str}: "{item["text"]}"{speaker_str}{stats_str}')
            elif id(item) in top_audio_items:
                label = item['label']
                prob = int(item['probability'] * 100)
                event_sec = item.get('event_time', 0)
                offset = item.get('offset', 0)
                time_info = f' ({secs_to_str(event_sec + offset)})'
                lines.append(f'  - {label}[{prob}%]{time_info}')
    else:
        lines.append('- **语音时间线**: 无')

    # 音乐（去重同曲目）
    if data['medias']:
        lines.append('- **音乐**:')
        seen_songs = set()
        for t, title, artist, state in data['medias']:
            key = f'{title}|{artist}'
            if key in seen_songs:
                continue
            seen_songs.add(key)
            artist_str = f' - {artist}' if artist else ''
            state_str = f' [{state}]' if state else ''
            lines.append(f'  - {t} "{title}"{artist_str}{state_str}')

    # App
    if data['apps']:
        app_strs = [f'{t} {name}' for t, name in data['apps']]
        lines.append(f'- **App**: {"; ".join(app_strs)}')

    # 通知（去重）
    if data['notifies']:
        seen_notify = set()
        unique_notifies = []
        for t, pkg, title, text in data['notifies']:
            key = f'{pkg}:{title}:{text[:30]}'
            if key not in seen_notify:
                seen_notify.add(key)
                unique_notifies.append((t, pkg, title, text))
        lines.append('- **通知**:')
        for t, pkg, title, text in unique_notifies:
            pkg_short = pkg.split('.')[-1] if '.' in pkg else pkg
            title_part = f'[{title}] ' if title else ''
            lines.append(f'  - {t} {pkg_short}: {title_part}{text}')

    # 输入
    if data['inputs']:
        for t, text in data['inputs']:
            lines.append(f'- **输入**: {t} "{text}"')

    # 用户网页消息
    if data['web_messages']:
        for t, text in data['web_messages']:
            lines.append(f'- **用户消息**: {t} "{text}"')

    # 任务触发
    if data['task_triggers']:
        for t, text in data['task_triggers']:
            lines.append(f'- **任务触发**: {t} {text}')

    # PC窗口
    if data['pc_windows']:
        # 去重显示（相同进程连续出现只记一次）
        seen_procs = set()
        pc_items = []
        for t, proc, title in data['pc_windows']:
            key = f'{proc}:{title[:30]}'
            if key not in seen_procs:
                seen_procs.add(key)
                title_str = f' ({title[:40]})' if title else ''
                pc_items.append(f'{t} {proc}{title_str}')
        if pc_items:
            lines.append(f'- **PC窗口**: {" | ".join(pc_items)}')

    # PC待机
    if data['pc_idle'] is not None:
        if data['pc_idle'] == 'idle':
            secs = data.get('pc_idle_seconds') or 0
            min_str = f'{int(secs/60)}分' if secs >= 60 else f'{secs}秒'
            lines.append(f'- **PC待机**: 待机中（{min_str}）')
        else:
            lines.append(f'- **PC待机**: 活跃')

    # HR快照（合并时段专用）
    if is_merged and hr_snap_str:
        lines.append(f'- **HR快照**: {hr_snap_str}')

    # 睡眠阶段（来自health.json）
    if sleep_data:
        stages = sleep_data.get('stages', [])
        if stages:
            slot_start_min = parse_time_to_minutes(slot_start)
            slot_end_min = parse_time_to_minutes(slot_end)
            if slot_start_min is not None and slot_end_min is not None:
                matched = []
                for st in stages:
                    t = st.get('t', '')
                    st_min = parse_time_to_minutes(t)
                    if st_min is not None:
                        if slot_start_min <= slot_end_min:
                            if slot_start_min <= st_min < slot_end_min:
                                matched.append(st)
                        else:
                            # 跨午夜（如 23:00~06:00）
                            if st_min >= slot_start_min or st_min < slot_end_min:
                                matched.append(st)
                if matched:
                    stage_parts = [f'{s["stage"]}({s["t"]})' for s in matched]
                    lines.append(f'- **睡眠阶段**: {" ".join(stage_parts)}')

    lines.append('')
    return '\n'.join(lines)


def build_merged_data(slots_sublist):
    """合并多个安静时段的数据"""
    merged = {
        'gps': None,
        'gps_location': None,
        'hr_values': [],
        'battery': None,
        'phone_battery': None,
        'screen_locked': None,
        'screen_times': [],
        'voice_timeline': [],
        'apps': [],
        'medias': [],
        'notifies': [],
        'inputs': [],
        'wifi_connected': None,
        'pc_windows': [],
        'pc_idle': None,
        'pc_idle_seconds': None,
    }
    for sk, d in slots_sublist:
        merged['voice_timeline'].extend(d['voice_timeline'])
        merged['hr_values'].extend(d['hr_values'])
        if d['battery'] is not None:
            merged['battery'] = d['battery']
        if d['phone_battery'] is not None:
            merged['phone_battery'] = d['phone_battery']
        if d['gps']:
            merged['gps'] = d['gps']
            merged['gps_location'] = d['gps_location']
        if d['screen_locked'] is not None:
            merged['screen_locked'] = d['screen_locked']
            merged['screen_times'].extend(d['screen_times'])
        if d['wifi_connected'] is not None:
            merged['wifi_connected'] = d['wifi_connected']
        if d['pc_windows']:
            merged['pc_windows'].extend(d['pc_windows'])
        if d['pc_idle'] is not None:
            merged['pc_idle'] = d['pc_idle']
            merged['pc_idle_seconds'] = d.get('pc_idle_seconds')
    return merged


def build_hr_snapshots(health_samples, start_slot, end_slot):
    """为合并时段构建HR快照（每30分钟一个）"""
    start_sec = seconds_since_midnight(start_slot + ':00')
    end_sec = seconds_since_midnight(end_slot + ':59')
    snapshots = []
    current_sec = (start_sec // 1800) * 1800
    while current_sec <= end_sec:
        h = current_sec // 3600
        m = (current_sec % 3600) // 60
        time_str = f'{h:02d}:{m:02d}'
        hr_info = get_health_hr_at_time(health_samples, time_str + ':00')
        if hr_info:
            snapshots.append(f'{hr_info[0]} HR={hr_info[1]}')
        current_sec += 1800
    return ', '.join(snapshots)


def main():
    if len(sys.argv) < 2:
        print('用法: python ai/analysis/fact_extractor.py <日期> [--hours <时段>] [--output <路径>]', file=sys.stderr)
        print('示例:', file=sys.stderr)
        print('  python ai/analysis/fact_extractor.py 2026-06-14', file=sys.stderr)
        print('  python ai/analysis/fact_extractor.py 2026-06-14 --hours 06:00~14:00', file=sys.stderr)
        print('  python ai/analysis/fact_extractor.py 2026-06-14 --output out.md', file=sys.stderr)
        sys.exit(1)

    date_str = sys.argv[1]
    time_range_str = None
    output_path = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--hours' and i + 1 < len(sys.argv):
            time_range_str = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # 默认输出
    if not output_path:
        output_path = os.path.join(_SCRIPT_DIR, '..', 'data', date_str, '事实-全天.md')

    print(f'加载感知数据: {date_str}', file=sys.stderr)
    events = load_perception(date_str)
    if events is None:
        sys.exit(1)

    health_data = load_health(date_str)
    health_samples = health_data.get('samples', [])
    sleep_data = health_data.get('sleep_data', {})

    print(f'原始事件: {len(events)}条', file=sys.stderr)
    if time_range_str:
        events = filter_events_by_time(events, time_range_str)
        print(f'时段过滤 [{time_range_str}]: {len(events)}条', file=sys.stderr)

    if not events:
        print('该时段无数据', file=sys.stderr)
        sys.exit(0)

    # 按5分钟时段分组
    slot_list = group_by_slot(events)
    print(f'时段数: {len(slot_list)}', file=sys.stderr)

    if not slot_list:
        print('无有效时段', file=sys.stderr)
        sys.exit(0)

    # 处理每个时段
    prev_state = {}
    processed_slots = []
    total_voice_count = 0

    for sk, evts in slot_list:
        data = collect_slot_data(evts, prev_state)
        processed_slots.append((sk, data))
        prev_state = {
            'gps': data['gps'],
            'gps_location': data['gps_location'],
            'screen_locked': data['screen_locked'],
            'wifi_connected': data['wifi_connected'],
            'pc_idle': data['pc_idle'],
            'pc_idle_seconds': data['pc_idle_seconds'],
        }
        total_voice_count += sum(1 for e in data['voice_timeline'] if e['type'] == 'speech')

    # 检测合并区间（连续3个以上安静时段）
    merge_ranges = []
    start_range = None
    for idx, (sk, data) in enumerate(processed_slots):
        if is_quiet_slot(data):
            if start_range is None:
                start_range = idx
        else:
            if start_range is not None:
                if idx - start_range >= 3:
                    merge_ranges.append((start_range, idx - 1))
                start_range = None
    if start_range is not None and len(processed_slots) - start_range >= 3:
        merge_ranges.append((start_range, len(processed_slots) - 1))

    # 构建输出段落
    final_sections = []
    used_indices = set()
    for mr_start, mr_end in merge_ranges:
        for idx in range(mr_start, mr_end + 1):
            used_indices.add(idx)

    # 生成非合并段落
    idx = 0
    while idx < len(processed_slots):
        # 检查是否在合并区间内
        in_merge = False
        for mr_start, mr_end in merge_ranges:
            if mr_start <= idx <= mr_end:
                if idx == mr_start:
                    # 构建合并段落
                    start_slot = processed_slots[mr_start][0]
                    end_slot = processed_slots[mr_end][0]
                    end_display = format_slot_end(end_slot)

                    sublist = processed_slots[mr_start:mr_end + 1]
                    merged_data = build_merged_data(sublist)
                    hr_snap_str = build_hr_snapshots(health_samples, start_slot, end_slot)

                    section_md = build_section_markdown(
                        start_slot, end_display, merged_data,
                        health_samples, is_merged=True, hr_snap_str=hr_snap_str,
                        sleep_data=sleep_data, date_str=date_str
                    )
                    final_sections.append(section_md)
                idx = mr_end + 1
                in_merge = True
                break

        if not in_merge:
            sk = processed_slots[idx][0]
            data = processed_slots[idx][1]
            end_display = format_slot_end(sk)
            section_md = build_section_markdown(sk, end_display, data, health_samples,
                                                sleep_data=sleep_data, date_str=date_str)
            final_sections.append(section_md)
            idx += 1

    # 生成最终Markdown
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    coverage = time_range_str if time_range_str else '全天'

    md_lines = [f'# {date_str} 事实数据', '']
    md_lines.append(f'> 生成时间: {now}')
    md_lines.append(f'> 数据覆盖: {coverage}')
    md_lines.append('')
    md_lines.extend(final_sections)
    md_lines.append('---')
    md_lines.append(f'共 {len(final_sections)} 个时段，{total_voice_count} 条语音')
    md_lines.append('')

    markdown = '\n'.join(md_lines)

    # 写入文件
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown)

    print(f'\n输出文件: {output_path}', file=sys.stderr)
    print(f'共 {len(final_sections)} 个时段，{total_voice_count} 条语音', file=sys.stderr)

    # 保存GPS缓存
    save_geo_cache()


if __name__ == '__main__':
    main()
