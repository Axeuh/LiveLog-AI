"""
提取精细时间线，按10分钟粒度输出
"""
import json
import os

date_str = '2026-06-07'
perception_file = os.path.join(os.path.dirname(__file__), '..', '..', 'ai', 'data', date_str, 'perception.jsonl')
health_file = os.path.join(os.path.dirname(__file__), '..', '..', 'ai', 'data', date_str, 'health.json')

# 加载事件
events = []
with open(perception_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line:
            try: events.append(json.loads(line))
            except: pass
events.sort(key=lambda e: e.get('t', ''))

# 加载健康数据
hr_data = {}
if os.path.exists(health_file):
    with open(health_file, 'r', encoding='utf-8') as f:
        health = json.load(f)
    for s in health.get('samples', []):
        ts = s.get('t_iso', '')
        if ts:
            hr_data[ts] = {'hr': s.get('hr'), 'steps': s.get('steps', 0),
                           'spo2': s.get('spo2'), 'stress': s.get('stress')}

def get_hr_at(time_str):
    """找time_str前后3分钟内的心率"""
    if ':' not in time_str:
        return None
    for ts, data in sorted(hr_data.items()):
        if time_str[:5] in ts:
            return data
    return None

# 按10分钟分组
from collections import defaultdict
buckets = defaultdict(list)
for e in events:
    t = e.get('t', '')
    if ':' in t:
        parts = t.split(':')
        # 归到5分钟粒度
        m = int(parts[1])
        m_rounded = (m // 5) * 5
        key = f"{parts[0]}:{m_rounded:02d}"
        buckets[key].append(e)

last_hr = None
last_app = None
last_song = None

for key in sorted(buckets.keys()):
    be = buckets[key]
    h, m = key.split(':')
    h_int, m_int = int(h), int(m)
    
    # 心率
    hr_vals = []
    for e in be:
        hr = e.get('hr') or (e.get('sensors') or {}).get('hr')
        if hr:
            hr_vals.append(hr)
    hr_str = ''
    if hr_vals:
        mn, mx = min(hr_vals), max(hr_vals)
        hr_str = f"{mn}-{mx}bpm" if mn != mx else f"{mn}bpm"
        last_hr = f"{mn}-{mx}bpm"
    elif last_hr:
        hr_str = last_hr
    
    # 语音
    voices = []
    for e in be:
        if e.get('type') != 'voice':
            continue
        text = e.get('text', '').strip()
        has = e.get('hasSpeech', False)
        if has and text and '<|nospeech|>' not in text and text not in ('.', '。', ''):
            clean = text.replace('<|nospeech|>', '').replace('<|Event_UNK|>','').strip()
            if len(clean) > 3:
                emo = e.get('emotion', '')
                segments = e.get('segments', [])
                if segments:
                    best = max(((s.get('emo',''), s.get('conf',0)) for s in segments), key=lambda x: x[1], default=('',0))
                    emo = best[0] if best[1] >= 0.3 else emo
                scene = e.get('scene', '') or e.get('scene_name', '')
                voices.append({'text': clean[:70], 'emotion': emo, 'scene': scene})
    
    # 媒体
    playing = [e for e in be if e.get('type') == 'media' and e.get('media_state') == 'playing']
    media_info = ''
    if playing:
        p = playing[-1]
        media_info = f"[{p.get('media_app','')}] {p.get('media_title','')[:25]} - {p.get('media_artist','')[:15]}"
    
    # App
    apps = sorted(set(e['app'] for e in be if e.get('type') == 'app'))
    app_change = ''
    if apps and (not last_app or apps[0] != last_app):
        app_change = apps[0]
    if apps:
        last_app = apps[0]
    
    has_activity = bool(hr_vals) or voices or playing or apps
    
    if has_activity:
        prefix = f"{key}  {hr_str:12s}"
        if media_info:
            print(f"{prefix}  {media_info}")
        if app_change:
            print(f"{prefix}  APP: {app_change}")
        for v in voices:
            emo_tag = f"({v['emotion']})" if v['emotion'] else ""
            scene_tag = f"[{v['scene']}]" if v['scene'] else ""
            print(f"{prefix}  VOICE{emo_tag} {v['text']}")
