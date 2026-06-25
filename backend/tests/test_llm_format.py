"""测试 voice-session 端点输出"""
import sys, json, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# 直接调用 Manager
from services.multimodal_audio_manager import get_multimodal_audio_manager

mgr = get_multimodal_audio_manager()
result = mgr.analyze(r"D:\Users\Axeuh\Desktop\Axeuh-server\server\Axeuh-home-system\multimodal-demo\models\test_mixes\test_alternating.wav")

print("=== analysis keys ===")
print(list(result.keys()))
print()

# 模拟精简处理（同 stt.py 的 voice-session 端点）
segments = result.get("segments", [])
audio_events = result.get("audio_events", [])

for seg in segments:
    seg.pop("emotion_emoji", None)
    seg.pop("confidence_pct", None)
    seg.pop("event_emoji", None)
    seg.pop("event_cn", None)
    seg.pop("all_events", None)
    scores = seg.get("emotion_scores", {})
    if scores:
        seg["emotion_scores"] = {k: v for k, v in scores.items() if v > 0.01}
    # PANNs 事件匹配
    seg_start = seg.get("start", 0)
    seg_end = seg.get("end", 0)
    seg_events = []
    for ev in (audio_events or []):
        ev_start = ev.get("start", 0)
        ev_end = ev.get("end", 0)
        if ev_start < seg_end and ev_end > seg_start:
            seg_events.append({
                "label": ev.get("label_cn", ev.get("label", "")),
                "prob": ev.get("probability", 0),
            })
    if seg_events:
        seg_events = [e for e in seg_events if e["prob"] >= 0.15]
        if seg_events:
            seg["scene_events"] = seg_events

print("=== segment keys (cleaned) ===")
print(list(segments[0].keys()))
print()

print("=== first segment ===")
print(json.dumps(segments[0], ensure_ascii=False, indent=2))
print()

# LLM 文本格式
print("=== llm_text ===")
for seg in segments:
    emo = seg.get("emotion_cn", "")
    conf = seg.get("confidence", 0)
    txt = seg.get("text", "")
    events = seg.get("scene_events", [])
    ev_labels = [e["label"] for e in events[:3]]
    suffix = f" [{', '.join(ev_labels)}]" if ev_labels else ""
    print(f"[{emo}]({conf:.0%}){suffix}: {txt}")

breaths = result.get("breath_events")
if breaths:
    desc = "、".join(f"{b.get('type_cn','')}({b.get('confidence',0):.0%})" for b in breaths[:3])
    print(f"[生理] {desc}")

print()
print("=== emotion_dist entry ===")
ed = result.get("emotion_distribution", [])
if ed:
    print({k: v for k, v in ed[0].items() if k not in ("emotion_emoji", "avg_confidence_pct")})
