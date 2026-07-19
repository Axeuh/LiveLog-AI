"""
当日感知数据分析脚本
用法: python analyze_day.py <YYYY-MM-DD>
输出: 结构化的分析摘要到 stdout
"""
import json
import sys
import os
from datetime import datetime
from collections import Counter, defaultdict

def analyze_perception(date_str):
    base = os.path.join(os.path.dirname(__file__), '..', '..', 'ai', 'data', date_str)
    perception_file = os.path.join(base, 'perception.jsonl')
    health_file = os.path.join(base, 'health.json')

    if not os.path.exists(perception_file):
        print(f"[ERROR] 找不到感知文件: {perception_file}")
        return

    print(f"=== {date_str} 感知数据分析报告 ===")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ---- 加载感知事件 ----
    events = []
    with open(perception_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except:
                    pass

    print(f"总事件数: {len(events)}")

    # ---- 按类型统计 ----
    type_counter = Counter()
    for e in events:
        t = e.get('type', 'unknown')
        type_counter[t] += 1

    print()
    print("## 事件类型分布")
    for t, c in type_counter.most_common():
        print(f"  {t}: {c}")

    # ---- 时间覆盖 ----
    times = []
    for e in events:
        t_str = e.get('t', '')
        if t_str and ':' in t_str:
            try:
                h, m, s = t_str.split(':')
                times.append(int(h) * 60 + int(m))
            except:
                pass

    if times:
        hour_range = set(t // 60 for t in times)
        hours = sorted(hour_range)
        print(f"\n## 时间覆盖")
        print(f"  活跃时段: {hours[0]:02d}:00 - {hours[-1]:02d}:00")
        print(f"  覆盖小时数: {len(hours)}")

    # ---- 媒体分析 ----
    media_entries = [e for e in events if e.get('type') == 'media']
    if media_entries:
        print(f"\n## 媒体播放记录 ({len(media_entries)} 条)")
        songs = []
        for m in media_entries:
            title = m.get('media_title', m.get('title', ''))
            artist = m.get('media_artist', m.get('artist', ''))
            app = m.get('media_app', m.get('app', ''))
            state = m.get('media_state', m.get('state', ''))
            if title:
                songs.append(f"    {m.get('t','')} [{app}] {title} - {artist} ({state})")
        for s in songs[:20]:  # 最多20首
            print(s)
        if len(songs) > 20:
            print(f"    ... 还有 {len(songs)-20} 条")

    # ---- App分析 ----
    app_entries = [e for e in events if e.get('type') == 'app']
    if app_entries:
        print(f"\n## App使用记录 ({len(app_entries)} 条)")
        apps = Counter()
        for a in app_entries:
            apps[a.get('app', 'unknown')] += 1
        for app_name, count in apps.most_common(10):
            print(f"  {app_name}: {count}次")

    # ---- 传感器分析 ----
    sensor_entries = [e for e in events if e.get('type') == 'sensor' or 'steps' in e or 'hr' in e]
    if sensor_entries:
        steps_vals = []
        hr_vals = []
        battery_vals = []
        phone_battery_vals = []
        for s in sensor_entries:
            # 检查顶层字段
            for key in ('steps', 'hr', 'battery'):
                val = s.get(key)
                if val is not None:
                    if key == 'steps':
                        steps_vals.append(val)
                    elif key == 'hr':
                        hr_vals.append(val)
                    elif key == 'battery':
                        battery_vals.append(val)
            # 检查 sensors 嵌套字段
            sensors = s.get('sensors', {})
            if sensors:
                for key in ('steps', 'hr', 'battery'):
                    val = sensors.get(key)
                    if val is not None:
                        if key == 'steps':
                            steps_vals.append(val)
                        elif key == 'hr':
                            hr_vals.append(val)
                        elif key == 'battery':
                            battery_vals.append(val)
            pb = s.get('phone_battery') or (s.get('sensors') or {}).get('phone_battery')
            if pb:
                phone_battery_vals.append(pb)

        print(f"\n## 传感器数据")
        if steps_vals:
            print(f"  步数: {max(steps_vals)} (最大值, {len(steps_vals)} 个采样)")
        if hr_vals:
            print(f"  心率: {min(hr_vals)}-{max(hr_vals)} bpm (n={len(hr_vals)})")
            avg_hr = sum(hr_vals) / len(hr_vals)
            print(f"  平均心率: {avg_hr:.0f} bpm")
        if battery_vals:
            print(f"  手表电量: {min(battery_vals)}%-{max(battery_vals)}%")
        if phone_battery_vals:
            print(f"  手机电量: {min(phone_battery_vals)}%-{max(phone_battery_vals)}%")

    # ---- Voice 分析 ----
    voice_entries = [e for e in events if e.get('type') == 'voice' or 'hasSpeech' in e]
    voice_with_speech = [v for v in voice_entries if v.get('hasSpeech') or (v.get('text','') and '<|nospeech|>' not in v.get('text',''))]
    if voice_with_speech:
        print(f"\n## 语音活动 ({len(voice_with_speech)} 条含有效语音)")
        emotions = Counter()
        for v in voice_with_speech:
            emo = v.get('emotion', '')
            if emo:
                emotions[emo] += 1
            segments = v.get('segments', [])
            for seg in segments:
                emo = seg.get('emo', '')
                if emo:
                    emotions[emo] += 1
        if emotions:
            print(f"  情绪分布: {dict(emotions.most_common())}")

    # ---- 健康数据 ----
    if os.path.exists(health_file):
        with open(health_file, 'r', encoding='utf-8') as f:
            health = json.load(f)
        samples = health.get('samples', [])

        # 提取心率时间序列
        hr_by_hour = defaultdict(list)
        steps_total = 0
        spo2_vals = []
        stress_vals = []

        for s in samples:
            hr = s.get('hr')
            ts = s.get('t_iso', '')
            if hr and ts:
                try:
                    h = int(ts.split(' ')[1].split(':')[0])
                    hr_by_hour[h].append(hr)
                except:
                    pass
            steps_total += s.get('steps', 0)
            spo2 = s.get('spo2')
            if spo2:
                spo2_vals.append(spo2)
            stress = s.get('stress')
            if stress:
                stress_vals.append(stress)

        print(f"\n## 健康数据")
        print(f"  总采样数: {len(samples)}")
        print(f"  心率有效采样: {sum(len(v) for v in hr_by_hour.values())}")
        print(f"  总步数(传感器累积): {steps_total}")
        if spo2_vals:
            print(f"  血氧: {min(spo2_vals)}%-{max(spo2_vals)}%")
        if stress_vals:
            print(f"  压力指数: {min(stress_vals)}-{max(stress_vals)} (低=放松)")

        # 每小时心率
        print(f"\n  每小时平均心率:")
        for h in sorted(hr_by_hour.keys()):
            vals = hr_by_hour[h]
            avg = sum(vals) / len(vals)
            bar = '|' * int(avg / 3)
            print(f"    {h:02d}:00  {avg:5.0f} bpm {bar}")

    print()
    print("=== 分析完毕 ===")


if __name__ == '__main__':
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')
    analyze_perception(date_str)
