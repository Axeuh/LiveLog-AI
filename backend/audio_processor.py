"""
音频处理模块
负责：语音识别ASR、情感识别SER、音频事件检测AED、环境声分类ESC
"""
import re
import logging
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---- 情绪标签映射 ----
EMOTION_MAP = {
    "<|HAPPY|>": "happy",
    "<|SAD|>": "sad",
    "<|ANGRY|>": "angry",
    "<|NEUTRAL|>": "neutral",
    "<|FEARFUL|>": "fearful",
    "<|DISGUSTED|>": "disgusted",
    "<|SURPRISED|>": "surprised",
    "<|EMO_UNKNOWN|>": "unknown",
}

EMOTION_CN = {
    "happy": "开心", "sad": "悲伤", "angry": "愤怒",
    "neutral": "中性", "fearful": "恐惧",
    "disgusted": "厌恶", "surprised": "惊讶",
    "unknown": "不确定",
}

EMOTION_EMOJI = {
    "happy": "😊", "sad": "😢", "angry": "😠",
    "neutral": "😐", "fearful": "😨",
    "disgusted": "🤢", "surprised": "😲",
    "unknown": "❓",
}

# 情绪伪置信度配置
# SenseVoice 不输出概率分数，因此基于 token 类型估算置信度
# 然后通过 PANNs 语音检测结果校准
EMOTION_BASE_CONFIDENCE = {
    "happy": 0.85, "sad": 0.85, "angry": 0.85,
    "neutral": 0.80, "fearful": 0.80,
    "disgusted": 0.80, "surprised": 0.80,
    "unknown": 0.35,
}

# 置信度校准：PANNs Speech 概率低于此值时打折
# 如果 PANNs 没检测到语音，情绪标签不太可信
SPEECH_THRESHOLD = 0.3  # P( Speech ) < 30% 时打折
CONFIDENCE_PENALTY = 0.6  # 打折系数

# ---- 事件标签映射 ----
EVENT_MAP = {
    "<|Speech|>": "speech", "<|BGM|>": "bgm",
    "<|Applause|>": "applause", "<|Laughter|>": "laughter",
    "<|Cry|>": "cry", "<|Sneeze|>": "sneeze",
    "<|Breath|>": "breath", "<|Cough|>": "cough",
}

EVENT_CN = {
    "speech": "说话", "bgm": "背景音乐", "applause": "鼓掌",
    "laughter": "笑声", "cry": "哭声", "sneeze": "打喷嚏",
    "breath": "叹气/深呼吸", "cough": "咳嗽",
}

EVENT_EMOJI = {
    "speech": "🎤", "bgm": "🎵", "applause": "👏",
    "laughter": "😂", "cry": "😭", "sneeze": "🤧",
    "breath": "💨", "cough": "🤭",
}

# ---- 语言标签（需要剥离）----
LANG_TOKENS = {"<|zh|>", "<|en|>", "<|ja|>", "<|ko|>", "<|yue|>",
               "<|ZH|>", "<|EN|>", "<|JA|>", "<|KO|>", "<|YUE|>"}

# ---- 其他特殊 token（ITN等）----
MISC_TOKENS = {"<|withitn|>", "<|withoutitn|>", "<|nocache|>", "<|withitn|>"}

# 编译正则 - 剥离所有特殊 token
TOKEN_PATTERN = re.compile(
    "|".join(
        re.escape(k) for k in (
            list(EMOTION_MAP.keys()) + list(EVENT_MAP.keys()) +
            list(LANG_TOKENS) + list(MISC_TOKENS)
        )
    )
)

# 情绪专用正则
EMOTION_RE = re.compile("|".join(re.escape(k) for k in EMOTION_MAP))
EVENT_RE = re.compile("|".join(re.escape(k) for k in EVENT_MAP))


def parse_sensevoice_text(text: str) -> dict:
    """解析 SenseVoice 输出的文本，提取情绪、事件、置信度和纯净文本。"""
    emotion_token = EMOTION_RE.search(text)
    if emotion_token:
        emotion = EMOTION_MAP.get(emotion_token.group(0), "neutral")
    else:
        emotion = "unknown"

    event_token = EVENT_RE.search(text)
    event = EVENT_MAP.get(event_token.group(0), None) if event_token else None

    # 检测所有事件 token（SenseVoice 可能输出多个，如 <|BGM|><|Breath|>）
    all_events = []
    for match in EVENT_RE.finditer(text):
        ev = EVENT_MAP.get(match.group(0))
        if ev and ev not in all_events:
            all_events.append(ev)

    # 事件优先级：speech < bgm < 生理事件 < 社交事件
    EVENT_PRIORITY = {"speech": 0, "bgm": 1, "breath": 2, "cough": 2,
                      "sneeze": 2, "cry": 3, "laughter": 3, "applause": 3}
    if all_events:
        all_events.sort(key=lambda e: EVENT_PRIORITY.get(e, 1), reverse=True)
        primary_event = all_events[0]  # 高优先级作为主事件
    else:
        primary_event = event

    # 置信度：基于情绪 token 类型估算
    confidence = EMOTION_BASE_CONFIDENCE.get(emotion, 0.5)

    # 剥离所有特殊 token
    clean = TOKEN_PATTERN.sub("", text).strip()

    return {
        "emotion": emotion,
        "emotion_cn": EMOTION_CN.get(emotion, emotion),
        "emotion_emoji": EMOTION_EMOJI.get(emotion, ""),
        "confidence": round(confidence, 2),
        "confidence_pct": f"{int(confidence * 100)}%",
        "event": primary_event,
        "event_cn": EVENT_CN.get(primary_event, primary_event) if primary_event else None,
        "event_emoji": EVENT_EMOJI.get(primary_event, "") if primary_event else None,
        "all_events": all_events,  # 所有检测到的事件
        "text": clean,
    }


class AudioProcessor:
    """SenseVoice + PANNs 音频分析器。延迟加载模型，一次加载重复使用。"""

    def __init__(self, device: str = "cuda:0", scene_analyzer: Any = None,
                 speaker_diarizer: Any = None, source_separator: Any = None,
                 tracks_output_dir: Optional[str] = None,
                 vad_processor: Any = None,
                 emotion_model: Any = None):
        self._model = None
        self.device = device
        self.scene_analyzer = scene_analyzer
        self.speaker_diarizer = speaker_diarizer
        self.source_separator = source_separator
        self.tracks_output_dir = tracks_output_dir
        self.vad_processor = vad_processor
        self.emotion_model = emotion_model  # emotion2vec+ 真实情绪模型
        self._last_vad_segments = None  # 保存 VAD 段供下游复用
        self.vad_processor = vad_processor

    def _load_model(self):
        """延迟加载模型（首次调用时加载）。"""
        if self._model is not None:
            return
        logger.info("正在加载 SenseVoice 模型（首次加载需下载模型文件，约1-3分钟）...")
        from funasr import AutoModel
        self._model = AutoModel(
            model="iic/SenseVoiceSmall",
            disable_update=True,
            device=self.device,
        )
        logger.info("SenseVoice 模型加载完成！")

    def _run_sensevoice(self, audio_path: str) -> tuple:
        """
        在单个音频上运行 SenseVoice，返回 (segments, emotion_counts, event_counts, duration)。

        Args:
            audio_path: 16kHz 单声道 WAV 路径

        Returns:
            (segments, emotion_counts, event_counts, effective_duration)
        """
        import soundfile as sf
        try:
            info = sf.info(audio_path)
            total_duration = round(info.duration, 1)
        except Exception:
            import librosa
            total_duration = round(librosa.get_duration(filename=audio_path), 1)

        # VAD 预分段（如果可用）
        if self.vad_processor is not None:
            from vad_processor import cut_audio_segment
            vad_segments = self.vad_processor.detect_segments(audio_path)
            self._last_vad_segments = vad_segments  # 保存供下游复用
            if len(vad_segments) > 1:
                logger.info(f"VAD 将音频切分为 {len(vad_segments)} 段，逐段运行 SenseVoice")
                return self._run_sensevoice_vad(audio_path, vad_segments, total_duration)

        raw_results = self._model.generate(
            input=audio_path,
            language="auto",
            use_itn=True,
            ban_emo_unk=True,
        )

        segments = []
        emotion_counts = {}
        event_counts = {}

        for item in raw_results if isinstance(raw_results, list) else []:
            text = item.get("text", "") if isinstance(item, dict) else ""
            ts = item.get("timestamp", None) if isinstance(item, dict) else None
            if not text:
                continue

            parsed = parse_sensevoice_text(text)
            if not parsed["text"]:
                continue

            start, end = 0.0, 0.0
            if ts and isinstance(ts, list) and len(ts) > 0:
                first = ts[0]
                if isinstance(first, (list, tuple)) and len(first) >= 2:
                    start = float(first[0]) / 1000.0
                    end = float(first[1]) / 1000.0
                elif isinstance(first, (int, float)):
                    start = 0.0
                    end = float(first) / 1000.0 if first > 100 else float(first)

            if end == 0.0 and segments:
                start = segments[-1]["end"]

            segment = {
                "start": round(start, 2),
                "end": round(end, 2),
                **parsed,
            }
            segments.append(segment)

            emotion_counts[parsed["emotion"]] = emotion_counts.get(parsed["emotion"], 0) + 1
            if parsed["event"] and parsed["event"] != "speech":
                event_counts[parsed["event"]] = event_counts.get(parsed["event"], 0) + 1

        # 修正时间戳
        if len(segments) == 1 and segments[0]["end"] == 0:
            segments[0]["end"] = total_duration
        if len(segments) > 1 and segments[-1]["end"] == 0:
            segments[-1]["end"] = total_duration
        if len(segments) > 1:
            for i in range(len(segments)):
                if segments[i]["end"] == 0 and i > 0:
                    segments[i]["end"] = segments[i + 1]["start"] if i + 1 < len(segments) else total_duration

        effective_duration = segments[-1]["end"] if segments else total_duration

        # PANNs 置信度校准（对每个 Segment 用 Speech 概率调整）
        self._calibrate_segment_confidence(segments, audio_path)

        return segments, emotion_counts, event_counts, effective_duration

    def _run_sensevoice_vad(
        self, audio_path: str, vad_segments: list, total_duration: float
    ) -> tuple:
        """
        按 VAD 分段逐段运行 SenseVoice，返回合并后的结果。
        vad_segments: [{start, end}, ...] 语音段列表
        """
        from vad_processor import cut_audio_segment

        all_segments = []
        emotion_counts = {}
        event_counts = {}

        for seg in vad_segments:
            seg_audio = cut_audio_segment(audio_path, seg["start"], seg["end"])
            if len(seg_audio) < 1600:  # 短于 0.1 秒跳过
                continue

            seg_len = len(seg_audio) / 16000.0
            seg_offset = seg["start"]

            raw_results = self._model.generate(
                input=seg_audio,
                language="auto",
                use_itn=True,
                ban_emo_unk=True,
            )

            for item in raw_results if isinstance(raw_results, list) else []:
                text = item.get("text", "") if isinstance(item, dict) else ""
                if not text:
                    continue

                parsed = parse_sensevoice_text(text)
                if not parsed["text"]:
                    continue

                # 时间戳：SenseVoice 返回的是相对于片段开头的（毫秒）
                # 我们加上片段偏移
                ts = item.get("timestamp", None) if isinstance(item, dict) else None
                if ts and isinstance(ts, list) and len(ts) > 0:
                    first = ts[0]
                    if isinstance(first, (list, tuple)) and len(first) >= 2:
                        start = float(first[0]) / 1000.0 + seg_offset
                        end = float(first[1]) / 1000.0 + seg_offset
                    elif isinstance(first, (int, float)):
                        start = seg_offset
                        end = seg_offset + seg_len
                else:
                    start = seg_offset
                    end = seg_offset + seg_len

                segment = {
                    "start": round(start, 2),
                    "end": round(end, 2),
                    **parsed,
                }
                all_segments.append(segment)

                emotion_counts[parsed["emotion"]] = emotion_counts.get(parsed["emotion"], 0) + 1
                if parsed["event"] and parsed["event"] != "speech":
                    event_counts[parsed["event"]] = event_counts.get(parsed["event"], 0) + 1

        # 按时间排序
        all_segments.sort(key=lambda s: s["start"])

        if not all_segments:
            all_segments.append({
                "start": 0.0, "end": total_duration,
                "text": "", "emotion": "unknown",
                "emotion_cn": "不确定", "confidence": 0.0,
                "event": None, "event_cn": None,
            })

        logger.info(f"VAD+ASR 完成: {len(all_segments)} 段")

        # PANNs 置信度校准
        self._calibrate_segment_confidence(all_segments, audio_path)

        return all_segments, emotion_counts, event_counts, total_duration

    def process(self, audio_path: str) -> Dict[str, Any]:
        """
        处理音频文件，返回结构化分析结果。

        返回格式:
        {
            "success": True,
            "duration": float,          # 总时长(秒)
            "segments": [
                {
                    "start": float,
                    "end": float,
                    "text": str,
                    "emotion": str,
                    "emotion_cn": str,
                    "emotion_emoji": str,
                    "event": str | None,
                    "event_cn": str | None,
                    "event_emoji": str | None,
                }
            ],
            "emotion_summary": dict,    # {emotion: count}
            "emotion_distribution": [], # [{emotion, count, percentage}]
            "event_summary": dict,      # {event: count}
            "dominant_emotion": str,
            "dominant_emotion_cn": str,
            "dominant_emotion_emoji": str,
        }
        """
        self._load_model()

        # 声源分离 + 逐轨分析（如果 SourceSeparator 已注入）
        if self.source_separator is not None:
            return self._process_with_separation(audio_path)

        # 标准流程：对原始音频运行 SenseVoice
        segments, emotion_counts, event_counts, effective_duration = \
            self._run_sensevoice(audio_path)

        self._log_segments_info(segments)
        self._calibrate_segment_confidence(segments, audio_path)

        result = self._build_result(
            segments, emotion_counts, event_counts, effective_duration
        )

        # 场景/环境声分析
        scene_result = self._run_scene_analysis(audio_path)
        if scene_result is not None:
            result["scene"] = scene_result

        # PANNs 详细音频事件检测（527 类 AudioSet）
        aed_result = self._run_aed_detection(audio_path)
        if aed_result is not None:
            result["audio_events"] = aed_result

        # 呼吸/叹气检测
        breath_result = self._run_breath_detection(audio_path)
        if breath_result:
            result["breath_events"] = breath_result

        # 说话人日志
        dia_result = self._run_speaker_diarization(audio_path, result.get("segments"))
        if dia_result is not None:
            result["speaker_diarization"] = dia_result
            if "segments" in dia_result:
                result["segments"] = dia_result["segments"]

        return result

    def _calibrate_segment_confidence(self, segments: list, audio_path: str):
        """
        用 emotion2vec+ 真实情绪概率校准情绪标签和置信度。
        同时用 PANNs Speech 概率做二次校准。
        """
        if not segments:
            return
        try:
            import librosa
            import numpy as np

            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            total_samples = len(audio)

            # emotion2vec+ 标签映射
            EMOTION2VEC_LABELS = ['angry', 'disgusted', 'fearful', 'happy',
                                  'neutral', 'other', 'sad', 'surprised', 'unknown']

            for seg in segments:
                s = int(seg["start"] * sr)
                e = min(int(seg["end"] * sr), total_samples)
                if e - s < sr // 2:  # 少于 0.5 秒不校准
                    continue
                clip = audio[s:e]

                # === 1. emotion2vec+ 真实情绪概率 ===
                if self.emotion_model is not None:
                    try:
                        emo_result = self.emotion_model.generate(
                            input=clip,  # 直接传 numpy array
                            output_dir="./outputs",
                        )
                        if isinstance(emo_result, list) and len(emo_result) > 0:
                            item = emo_result[0] if isinstance(emo_result[0], dict) else None
                            if item and "scores" in item and "labels" in item:
                                scores = item["scores"]
                                labels = item["labels"]
                                if scores and labels:
                                    best_idx = int(np.argmax(scores))
                                    best_label_raw = labels[best_idx].split('/')[-1]  # "开心/happy" -> "happy"
                                    best_score = float(scores[best_idx])

                                    # 更新情绪标签和置信度
                                    if best_label_raw in EMOTION_MAP.values():
                                        seg["emotion"] = best_label_raw
                                        seg["emotion_cn"] = EMOTION_CN.get(best_label_raw, best_label_raw)
                                        seg["emotion_emoji"] = EMOTION_EMOJI.get(best_label_raw, "")
                                    seg["confidence"] = round(best_score, 2)
                                    seg["confidence_pct"] = f"{int(best_score * 100)}%"
                                    seg["emotion_scores"] = {
                                        labels[i].split('/')[-1]: round(float(scores[i]), 3)
                                        for i in range(len(labels))
                                    }
                    except Exception as e:
                        logger.warning(f"emotion2vec+ 单段推理失败: {e}")
                        # 回退到 PANNs 校准
                        self._panns_speech_calibration(seg, audio, sr, s, e)

                # === 2. PANNs Speech 概率二次校准 ===
                if self.scene_analyzer is not None:
                    self._panns_speech_calibration(seg, audio, sr, s, e)

        except Exception as e:
            # k2_fsa 可选依赖缺失时 speechbrain 会抛 Lazy import 异常，不影响核心功能
            logger.debug(f"置信度校准跳过（可选）: {e}")

    def _panns_speech_calibration(self, seg: dict, audio: np.ndarray,
                                   sr: int, s: int, e: int):
        """PANNs Speech 概率校准（仅当 emotion2vec+ 未覆盖时作为后备）"""
        if self.scene_analyzer is None:
            return
        try:
            import torch
            from sound_scene import compute_logmel
            import numpy as np

            clip = audio[s:e]
            clip_dur = max(len(clip) / sr, 1.0)
            n_samples = int(clip_dur * sr)
            if len(clip) < n_samples:
                clip = np.pad(clip, (0, n_samples - len(clip)))
            else:
                clip = clip[:n_samples]

            logmel = compute_logmel(clip, sr=16000)
            logmel_tensor = torch.from_numpy(logmel).to(self.device)
            with torch.no_grad():
                probs = self.scene_analyzer._model(logmel_tensor)
            probs_np = probs.cpu().numpy().flatten()

            speech_prob = float(probs_np[0]) if len(probs_np) > 0 else 0
            base_conf = seg.get("confidence", 0.8)
            if speech_prob < SPEECH_THRESHOLD:
                penalty = max(speech_prob / SPEECH_THRESHOLD, 0.2)
                cal_conf = base_conf * penalty * CONFIDENCE_PENALTY
            else:
                cal_conf = min(base_conf * 1.1, 0.95)
            seg["confidence"] = round(cal_conf, 2)
            seg["confidence_pct"] = f"{int(cal_conf * 100)}%"
            seg["speech_prob"] = round(speech_prob, 3)
        except Exception:
            pass

    def _log_segments_info(self, segments: list):
        """日志输出 segments 统计信息。"""
        if segments:
            n_neutral = sum(1 for s in segments if s.get("emotion") == "neutral")
            n_emotional = len(segments) - n_neutral
            logger.info(
                f"ASR 完成: {len(segments)} 段, "
                f"{n_emotional} 段带情绪, "
                f"时长 {segments[-1]['end']:.1f}s"
            )

    def _build_result(
        self, segments: list, emotion_counts: dict,
        event_counts: dict, effective_duration: float
    ) -> dict:
        """从 SenseVoice 结果构建标准返回结构。"""
        total_segments = len(segments) or 1
        emotion_distribution = []
        for k, v in sorted(emotion_counts.items(), key=lambda x: -x[1]):
            seg_confs = [s["confidence"] for s in segments if s["emotion"] == k]
            avg_conf = round(sum(seg_confs) / len(seg_confs), 2) if seg_confs else 0.5
            emotion_distribution.append({
                "emotion": k,
                "emotion_cn": EMOTION_CN.get(k, k),
                "emotion_emoji": EMOTION_EMOJI.get(k, ""),
                "count": v,
                "percentage": round(v / total_segments * 100),
                "avg_confidence": avg_conf,
                "avg_confidence_pct": f"{int(avg_conf * 100)}%",
            })

        dominant = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "unknown"

        # 事件详情：主事件 + all_events 中的非 speech 事件
        event_details = []
        for s in segments:
            # 主事件
            if s["event"] and s["event"] != "speech":
                event_details.append({
                    "event": s["event"],
                    "event_cn": s["event_cn"],
                    "event_emoji": s["event_emoji"],
                    "confidence": s.get("confidence", 0.5),
                    "confidence_pct": s.get("confidence_pct", "50%"),
                    "time": s["start"],
                    "time_str": f"{int(s['start']//60):02d}:{int(s['start']%60):02d}",
                    "text": s["text"],
                })
            # all_events 中的额外事件（如 breath + bgm 同时出现）
            all_ev = s.get("all_events", [])
            for ae in all_ev:
                if ae not in ("speech", "bgm") and ae != s.get("event"):
                    event_details.append({
                        "event": ae,
                        "event_cn": EVENT_CN.get(ae, ae),
                        "event_emoji": EVENT_EMOJI.get(ae, ""),
                        "confidence": s.get("confidence", 0.5),
                        "confidence_pct": s.get("confidence_pct", "50%"),
                        "time": s["start"],
                        "time_str": f"{int(s['start']//60):02d}:{int(s['start']%60):02d}",
                        "text": f"({s.get('event_cn', '')}) {s['text']}",
                    })

        return {
            "success": True,
            "duration": effective_duration,
            "duration_str": f"{int(effective_duration//60)}分{int(effective_duration%60)}秒",
            "segments": segments,
            "emotion_summary": emotion_counts,
            "emotion_distribution": emotion_distribution,
            "event_summary": event_counts,
            "event_details": event_details,
            "dominant_emotion": dominant,
            "dominant_emotion_cn": EMOTION_CN.get(dominant, dominant),
            "dominant_emotion_emoji": EMOTION_EMOJI.get(dominant, ""),
        }

    def _run_scene_analysis(
        self, audio_path: str, time_segments: Optional[List[Dict[str, float]]] = None
    ) -> Optional[dict]:
        """
        运行 PANNs 场景/环境声分析。

        Args:
            audio_path: 音频路径
            time_segments: VAD 时间段，不传则使用 _last_vad_segments

        Returns:
            scene 数据字典
        """
        if self.scene_analyzer is None:
            return None
        try:
            # 优先使用传入的 time_segments，否则用缓存的 VAD 段
            if time_segments is None:
                time_segments = self._last_vad_segments
            # 如果有 VAD 分段，按段分类（场景随时间变化）
            if time_segments and len(time_segments) > 1:
                logger.info(f"正在按 {len(time_segments)} 个时间段运行场景分析...")
                timeline = self.scene_analyzer.classify_scene_timeline(
                    audio_path, time_segments, top_k=3
                )
                # 全局平均分类仍然保留作为概览
                global_result = self.scene_analyzer.classify_scene(audio_path, top_k=5)
                scene_result = {
                    "scene_tags": global_result.get("scene_tags", []),
                    "scene_groups": global_result.get("scene_groups", {}),
                    "scene_primary": global_result.get("scene_primary"),
                    "timeline": timeline,
                }
                # 场景变化检测
                if len(timeline) > 1:
                    changes = []
                    for j in range(1, len(timeline)):
                        prev = timeline[j - 1]
                        curr = timeline[j]
                        if prev["primary"] and curr["primary"]:
                            prev_label = prev["primary"].get("label", "")
                            curr_label = curr["primary"].get("label", "")
                            if prev_label != curr_label and prev_label and curr_label:
                                changes.append({
                                    "time": curr["start"],
                                    "from": prev["primary"].get("label_cn", prev_label),
                                    "to": curr["primary"].get("label_cn", curr_label),
                                })
                    if changes:
                        scene_result["scene_changes"] = changes
                        logger.info(f"场景变化: {len(changes)} 次")
                logger.info(f"场景时间线分析完成: {len(timeline)} 段")
            else:
                logger.info("正在运行 PANNs 环境声分析...")
                scene_result = self.scene_analyzer.classify_scene(audio_path, top_k=5)
                logger.info("环境声分析完成")
            return scene_result
        except Exception as e:
            logger.warning(f"环境声分析失败: {e}")
            import traceback
            logger.warning(f"环境声分析traceback:\n{traceback.format_exc()}")
            return {"error": str(e)}

    def _run_aed_detection(self, audio_path: str) -> Optional[List[Dict]]:
        """运行 PANNs 音频事件检测，返回详细事件列表。"""
        if self.scene_analyzer is None:
            return None
        try:
            logger.info("正在运行 PANNs 音频事件检测 (527 类)...")
            segments = self.scene_analyzer.classify_segments(
                audio_path, segment_duration=2.0, top_k=5
            )
            # 收集所有窗口的所有事件（过滤低概率）
            all_events = []
            for seg in segments:
                if not seg.get("events"):
                    continue
                for ev in seg["events"]:
                    prob = ev["probability"]
                    if prob < 0.08:  # 过滤 < 8%（PANNs 概率天然偏低）
                        continue
                    all_events.append({
                        "time": seg["time"],
                        "label": ev["label"],
                        "label_cn": ev.get("label_cn", ev["label"]),
                        "probability": prob,
                        "probability_pct": ev["probability_pct"],
                        "duration": seg["duration"],
                    })

            if not all_events:
                return None

            # 按标签分组，每组内合并相邻窗口
            from collections import OrderedDict
            by_label = OrderedDict()
            for ev in sorted(all_events, key=lambda x: x["time"]):
                label = ev["label"]
                if label not in by_label:
                    by_label[label] = []
                by_label[label].append(ev)

            merged = []
            for label, evs in by_label.items():
                # 合并连续窗口
                merged_evs = []
                current = None
                for ev in evs:
                    if current is None:
                        current = {**ev}
                        del current["time"]
                        current["start"] = ev["time"]
                        current["end"] = ev["time"] + ev["duration"]
                        current["count"] = 1
                    elif ev["time"] - current["end"] <= 1.5:
                        current["end"] = ev["time"] + ev["duration"]
                        current["count"] += 1
                        # 取最高概率
                        if ev["probability"] > current["probability"]:
                            current["probability"] = ev["probability"]
                            current["probability_pct"] = ev["probability_pct"]
                    else:
                        merged_evs.append(current)
                        current = {**ev}
                        del current["time"]
                        current["start"] = ev["time"]
                        current["end"] = ev["time"] + ev["duration"]
                        current["count"] = 1
                if current:
                    merged_evs.append(current)

                # 过滤太短的事件
                for m in merged_evs:
                    if m["end"] - m["start"] >= 1.0:
                        merged.append({
                            "start": round(m["start"], 1),
                            "end": round(m["end"], 1),
                            "label": label,
                            "label_cn": m["label_cn"],
                            "probability": round(m["probability"], 2),
                            "probability_pct": m["probability_pct"],
                            "count": m["count"],
                        })

            merged.sort(key=lambda x: x["start"])
            logger.info(f"音频事件检测完成: {len(merged)} 条事件")
            return merged if merged else None
        except Exception as e:
            logger.warning(f"音频事件检测失败: {e}")
            import traceback
            logger.warning(f"音频事件检测traceback:\n{traceback.format_exc()}")
            return [{"error": str(e)}]

    def _run_breath_detection(self, audio_path: str) -> Optional[List[Dict]]:
        """运行呼吸/叹气检测。"""
        try:
            import librosa
            from sigh_detector import detect_breaths
            audio, sr = librosa.load(audio_path, sr=16000, mono=True)
            # 获取 VAD 段用于掩码（减少误报）
            vad_timeline = None
            if self.vad_processor is not None:
                try:
                    vad_segs = self.vad_processor.detect_segments(audio_path)
                    if vad_segs and len(vad_segs) > 1:
                        vad_timeline = [{"start": s["start"], "end": s["end"]}
                                        for s in vad_segs]
                except Exception:
                    pass
            events = detect_breaths(audio, sr=16000, vad_timeline=vad_timeline)
            return events if events else None
        except Exception as e:
            logger.warning(f"呼吸/叹气检测失败: {e}")
            return None

    def _run_speaker_diarization(
        self, audio_path: str, segments: Optional[list] = None
    ) -> Optional[dict]:
        """运行说话人日志分析，返回说话人数据或 None。同时使用 PANNs 估算性别。"""
        if self.speaker_diarizer is None:
            return None
        try:
            logger.info("正在运行说话人日志分析...")
            dia_result = self.speaker_diarizer.diarize(audio_path)
            if dia_result.get("success"):
                result = {
                    "n_speakers": dia_result["n_speakers"],
                    "timeline": dia_result["timeline"],
                }
                # 使用 PANNs 估算每个说话人的性别（从音频对应段提取）
                if self.scene_analyzer is not None and dia_result.get("timeline"):
                    result["speaker_genders"] = self._estimate_speaker_genders(
                        audio_path, dia_result["timeline"]
                    )
                    # 注入到 timeline
                    genders = result.get("speaker_genders", {})
                    for t in result["timeline"]:
                        spk = t.get("speaker_label") or f"说话人 {t['speaker'] + 1}"
                        if spk in genders:
                            t["gender"] = genders[spk]
                    logger.info(f"性别识别: {genders}")
                # 对齐说话人到 ASR 段（如有）
                if segments and self.source_separator is None:
                    result["segments"] = self.speaker_diarizer.align_with_segments(
                        dia_result, segments
                    )
                logger.info(
                    f"说话人日志完成: {dia_result['n_speakers']} 个说话人"
                )
                return result
            return None
        except Exception as e:
            logger.warning(f"说话人日志分析失败: {e}")
            return {"error": str(e)}

    def _estimate_speaker_genders(self, audio_path: str, timeline: list) -> dict:
        """
        使用 PANNs 估算每个说话人的性别。
        对每个说话人的所有音频段提取 PANNs 概率，取 Male/Female 均值。

        Returns:
            {"说话人 1": "男性", "说话人 2": "女性", ...}
        """
        import librosa
        import soundfile as sf
        from sound_scene import compute_logmel
        import torch
        import numpy as np

        # 加载全音频
        audio, sr = librosa.load(audio_path, sr=16000, mono=True)
        total_samples = len(audio)

        # 按说话人聚合
        speaker_segments = {}
        for t in timeline:
            spk = t.get("speaker_label") or f"说话人 {t['speaker'] + 1}"
            if spk not in speaker_segments:
                speaker_segments[spk] = []
            speaker_segments[spk].append((t["start"], t["end"]))

        genders = {}
        for spk, segs in speaker_segments.items():
            male_probs = []
            female_probs = []
            for start_s, end_s in segs:
                s = int(start_s * sr)
                e = min(int(end_s * sr), total_samples)
                if e - s < sr // 2:  # 少于 0.5 秒跳过
                    continue
                clip = audio[s:e]
                # pad 到整秒
                n_samples = int(max(len(clip) / sr, 1.0) * sr)
                if len(clip) < n_samples:
                    clip = np.pad(clip, (0, n_samples - len(clip)))
                else:
                    clip = clip[:n_samples]

                logmel = compute_logmel(clip, sr=16000)
                logmel_tensor = torch.from_numpy(logmel).to(self.device)
                with torch.no_grad():
                    probs = self.scene_analyzer._model(logmel_tensor)
                probs_np = probs.cpu().numpy().flatten()

                # AudioSet: index 1 = Male speech, 2 = Female speech
                male_probs.append(float(probs_np[1]) if len(probs_np) > 1 else 0)
                female_probs.append(float(probs_np[2]) if len(probs_np) > 2 else 0)

            if not male_probs:
                genders[spk] = "未知"
            else:
                avg_male = np.mean(male_probs)
                avg_female = np.mean(female_probs)
                # 阈值0.1以上才判断，否则未知
                if avg_male > 0.1 and avg_male > avg_female:
                    genders[spk] = "男性"
                elif avg_female > 0.1 and avg_female > avg_male:
                    genders[spk] = "女性"
                else:
                    genders[spk] = "未知"

        return genders

    def _process_with_separation(self, audio_path: str) -> dict:
        """
        声源分离处理流程：
        1. 分离音频为多个说话人音轨
        2. 每个音轨独立运行 SenseVoice
        3. 合并结果
        """
        logger.info("=== 声源分离模式 ===")
        import os, tempfile
        import soundfile as sf

        # 检查音频时长，SepFormer 对长音频耗时陡增
        try:
            info = sf.info(audio_path)
            audio_dur = info.duration
        except Exception:
            audio_dur = 0
        MAX_SEP_DURATION = 30  # 超过 30 秒跳过声源分离
        if audio_dur > MAX_SEP_DURATION:
            logger.warning(
                f"音频过长 ({audio_dur:.0f}s > {MAX_SEP_DURATION}s)，"
                f"跳过声源分离，使用标准流程 + 说话人日志"
            )
            segments, ec, evc, dur = self._run_sensevoice(audio_path)
            self._log_segments_info(segments)
            result = self._build_result(segments, ec, evc, dur)
            result["source_separation"] = {
                "error": f"音频过长 ({audio_dur:.0f}s)，已跳过声源分离"
            }
            # 仍然运行场景分析、事件检测和说话人日志
            scene_result = self._run_scene_analysis(audio_path)
            if scene_result is not None:
                result["scene"] = scene_result
            aed_result = self._run_aed_detection(audio_path)
            if aed_result is not None:
                result["audio_events"] = aed_result
            breath_result = self._run_breath_detection(audio_path)
            if breath_result:
                result["breath_events"] = breath_result
            dia_result = self._run_speaker_diarization(audio_path, result.get("segments"))
            if dia_result is not None:
                result["speaker_diarization"] = dia_result
            return result

        # 1. 声源分离
        sep_result = self.source_separator.separate(audio_path)
        if not sep_result.get("success") or sep_result.get("n_sources", 0) < 1:
            logger.warning("声源分离失败，回退到标准流程")
            segments, ec, evc, dur = self._run_sensevoice(audio_path)
            self._log_segments_info(segments)
            result = self._build_result(segments, ec, evc, dur)
            result["source_separation"] = {"error": "分离失败，使用混合音频分析"}
            return result

        # 2. 逐轨处理（音轨持久化存储）
        tracks = []
        all_segments = []
        global_emotion_counts = {}
        global_event_counts = {}
        effective_duration = sep_result["duration"]

        # 创建持久化音轨目录
        import uuid
        session_id = str(uuid.uuid4())[:8]
        if self.tracks_output_dir:
            track_dir = os.path.join(self.tracks_output_dir, session_id)
            os.makedirs(track_dir, exist_ok=True)
        else:
            track_dir = None

        for src in sep_result["sources"]:
            track_path = os.path.join(
                track_dir or tempfile.mkdtemp(),
                f"track_{src['track_index']}.wav"
            )
            sf.write(track_path, src["waveform"], 16000)

            logger.info(f"分析 {src['label']} (能量={src['energy']:.4f})...")
            segs, ec, evc, _ = self._run_sensevoice(track_path)

            # 标记说话人来源
            for seg in segs:
                seg["source_track"] = src["track_index"]
                seg["source_label"] = src["label"]

            # 计算该轨道的情绪分布
            total = len(segs) or 1
            track_emotion_dist = []
            for k, v in sorted(ec.items(), key=lambda x: -x[1]):
                track_emotion_dist.append({
                    "emotion": k,
                    "emotion_cn": EMOTION_CN.get(k, k),
                    "count": v,
                    "percentage": round(v / total * 100),
                })

            track_url = f"/tracks/{session_id}/track_{src['track_index']}.wav" if track_dir else None

            tracks.append({
                "track_index": src["track_index"],
                "label": src["label"],
                "energy": src["energy"],
                "n_segments": len(segs),
                "track_url": track_url,
                "segments": segs,
                "emotion_distribution": track_emotion_dist,
                "dominant_emotion": max(ec, key=ec.get) if ec else "unknown",
                "dominant_emotion_cn": EMOTION_CN.get(
                    max(ec, key=ec.get) if ec else "unknown", "未知"
                ),
            })

            all_segments.extend(segs)
            for k, v in ec.items():
                global_emotion_counts[k] = global_emotion_counts.get(k, 0) + v
            for k, v in evc.items():
                global_event_counts[k] = global_event_counts.get(k, 0) + v

            # 如果未配置持久化目录，清理临时文件
            if track_dir is None:
                try:
                    os.remove(track_path)
                except OSError:
                    pass

        # 按时间排序所有段
        all_segments.sort(key=lambda s: s["start"])

        logger.info(f"声源分离完成: {len(tracks)} 轨, {len(all_segments)} 段")

        # 构建结果
        result = self._build_result(
            all_segments, global_emotion_counts,
            global_event_counts, effective_duration
        )
        result["source_separation"] = {
            "enabled": True,
            "n_sources": len(tracks),
            "tracks": tracks,
        }

        # 场景/环境声分析（对原始混合音频）
        scene_result = self._run_scene_analysis(audio_path)
        if scene_result is not None:
            result["scene"] = scene_result

        # 详细音频事件检测
        aed_result = self._run_aed_detection(audio_path)
        if aed_result is not None:
            result["audio_events"] = aed_result

        # 呼吸/叹气检测
        breath_result = self._run_breath_detection(audio_path)
        if breath_result:
            result["breath_events"] = breath_result

        # 说话人日志（对原始混合音频，不覆盖分离后的 segments 标签）
        if self.speaker_diarizer is not None:
            try:
                logger.info("正在对原始音频运行说话人日志分析...")
                dia_result = self.speaker_diarizer.diarize(audio_path)
                if dia_result.get("success"):
                    # 仅添加说话人日志信息，不覆盖分离后的 segment 标签
                    result["speaker_diarization"] = {
                        "n_speakers": dia_result["n_speakers"],
                        "timeline": dia_result["timeline"],
                        "note": "此数据基于原始混合音频，分离音轨已按声源标注",
                    }
                    logger.info(f"说话人日志完成: {dia_result['n_speakers']} 个说话人")
            except Exception as e:
                logger.warning(f"说话人日志分析失败: {e}")
                result["speaker_diarization"] = {"error": str(e)}

        return result
