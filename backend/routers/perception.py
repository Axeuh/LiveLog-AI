# -*- coding: utf-8 -*-
"""
感知数据接收路由

手机 App (DataCollectorService) 通过此模块上报感知事件和音频数据。
感知事件写入 ai/data/{date}/perception.jsonl，供 AI 分析系统消费。
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel, Field
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/screen/stt", tags=["perception"])


class PerceptionEventRequest(BaseModel):
    """感知事件独立上报"""
    type: str = Field(..., description="事件类型: notify/app/media/sensor/screen/input/device_env")
    payload: Dict[str, Any] = Field(..., description="事件数据")
    ts: Optional[str] = Field(None, description="事件时间，不传用 now")


@router.post("/perception-event")
async def perception_event(req: PerceptionEventRequest):
    """
    感知事件独立上报。
    App 在事件发生时立即调用，不等采集周期。
    """
    from services.perception_store import append_perception
    from datetime import datetime, timezone, timedelta
    try:
        ts = req.ts or datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
        entry = {"type": req.type, "t": ts}
        entry.update(req.payload)
        append_perception(entry, auto_type=False)

        # 构建可读日志摘要（截断 payload 避免刷屏）
        payload_summary = {}
        for k, v in req.payload.items():
            if isinstance(v, str) and len(v) > 80:
                payload_summary[k] = v[:80] + "..."
            elif isinstance(v, (list, dict)):
                payload_summary[k] = f"{type(v).__name__}({len(v)})"
            else:
                payload_summary[k] = v
        logger.info(f"[PerceptionEvent] type={req.type} ts={ts} payload={json.dumps(payload_summary, ensure_ascii=False)}")

        return {"status": "ok", "type": req.type}
    except Exception as e:
        logger.error(f"[PerceptionEvent] 处理失败: {e}")
        return {"status": "error", "message": str(e)}


class VoiceSessionRequest(BaseModel):
    """语音对话请求"""
    audio: Optional[str] = Field(None, description="Base64 编码的音频数据")
    text: Optional[str] = Field(None, description="识别后的文本（如果已有）")
    ts: Optional[str] = Field(None, description="音频时间")


@router.post("/voice-session")
async def voice_session(req: VoiceSessionRequest):
    """
    接收手机端语音数据和感知上下文（JSON 格式，音频 Base64 编码）。
    音频保存到后端 data/audio/ 供后续分析，文本写入 perception.jsonl。
    """
    return await _handle_voice_session(req.audio, req.text, req.ts)


@router.post("/voice-session-multipart")
async def voice_session_multipart(
    file: UploadFile = File(None),
    client_time: str = Form(""),
    mode: str = Form("listen"),
):
    """
    接收手机端语音数据和感知上下文（multipart/form-data 格式）。
    与 voice-session 功能相同，只是输入格式不同。
    """
    audio_base64 = None
    if file and file.filename:
        try:
            audio_bytes = await file.read()
            if audio_bytes:
                import base64
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            logger.warning(f"[VoiceSession] 读取上传文件失败: {e}")

    return await _handle_voice_session(audio_base64, "", client_time)


async def _handle_voice_session(audio: Optional[str], text: Optional[str], ts: Optional[str]) -> Dict[str, Any]:
    """语音会话处理核心逻辑（JSON 和 multipart 共用）"""
    from services.perception_store import save_audio, append_perception
    from datetime import datetime, timezone, timedelta
    import base64
    import asyncio
    import os

    try:
        ts_val = ts or datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")

        # 如果有音频数据（Base64），保存到文件
        audio_path = None
        audio_size_kb = 0
        if audio:
            try:
                audio_bytes = base64.b64decode(audio)
                audio_size_kb = len(audio_bytes) // 1024
                path = save_audio(audio_data=audio_bytes)
                if path:
                    audio_path = path
            except Exception as e:
                logger.warning(f"[VoiceSession] 保存音频失败: {e}")

        # 如果有文本，写入感知数据
        text_preview = ""
        if text:
            text_preview = text[:120] + ("..." if len(text) > 120 else "")
            voice_entry = {
                "type": "voice",
                "t": ts_val,
                "hasSpeech": True,
                "segments": [{
                    "start": 0.0,
                    "end": 0.0,
                    "text": text,
                    "avg_db": -50.0,
                    "emotion_tag": "neutral",
                    "emotion_prob": 0.5,
                }],
            }
            if audio_path:
                voice_entry["audio"] = audio_path
            append_perception(voice_entry, auto_type=False)

        logger.info(f"[VoiceSession] ts={ts_val} audio={audio_size_kb}KB text={len(text or '')}ch preview=\"{text_preview}\"")

        # 后台启动音频感知分析（不阻塞响应）
        if audio_path:
            from config.config import get_config
            abs_audio_path = os.path.join(get_config().DATA_DIR, audio_path)
            _trigger_audio_analysis(abs_audio_path, ts_val)

        return {
            "status": "ok",
            "audio_saved": bool(audio_path),
            "text_received": bool(text),
        }
    except Exception as e:
        logger.error(f"[VoiceSession] 处理失败: {e}")
        return {"status": "error", "message": str(e)}


def _trigger_audio_analysis(audio_path: str, ts_val: str) -> None:
    """在后台线程中运行完整音频感知分析并记录日志"""
    import threading
    import os

    # 去重：同一文件 60 秒内只分析一次
    _analyzed_cache: set = getattr(_trigger_audio_analysis, "_cache", set())
    _trigger_audio_analysis._cache = _analyzed_cache
    if audio_path in _analyzed_cache:
        return
    _analyzed_cache.add(audio_path)
    # 60 秒后从缓存移除
    threading.Timer(60, lambda: _analyzed_cache.discard(audio_path)).start()

    def _run():
        try:
            from services.multimodal_audio_manager import get_multimodal_audio_manager
            from services.perception_store import append_perception
            from config.config import get_config

            if not os.path.exists(audio_path):
                logger.warning(f"[AudioAnalysis] 音频文件不存在: {audio_path}")
                return

            # 检查音频格式，非 WAV 则转换
            if not _ensure_wav(audio_path):
                logger.warning(f"[AudioAnalysis] 音频格式不支持且无法转换，跳过分析: {os.path.basename(audio_path)}")
                return

            mgr = get_multimodal_audio_manager()
            result = mgr.analyze(audio_path)

            # 提取关键结果
            asr_text = result.get("asr_text", "") or ""
            # 如果顶层 asr_text 为空，从 segments 取
            if not asr_text:
                seg_texts = [s.get("text", "") for s in result.get("segments", []) if s.get("text")]
                if seg_texts:
                    asr_text = seg_texts[0]
            scene = result.get("scene", "")
            audio_events = result.get("audio_events", [])
            emotion = result.get("emotion", {})
            speaker = result.get("speaker", {})
            segments = result.get("segments", [])
            silent = result.get("silent", False)
            vad_segments = result.get("vad_segments", [])

            # 声纹匹配（与原项目一致：VAD子段+滑动窗口+统计）
            if segments and os.path.exists(audio_path):
                try:
                    import numpy as np
                    import soundfile as sf
                    from services.voiceprint_service import get_voiceprint_service
                    vp_svc = get_voiceprint_service()
                    if vp_svc and vp_svc.is_ready() and vp_svc.get_speaker_count() > 0:
                        audio_full, fs = sf.read(audio_path)
                        for seg in segments:
                            seg_start = seg.get("start", 0)
                            seg_end = seg.get("end", 0)
                            s_sample = int(seg_start * fs)
                            e_sample = int(seg_end * fs)
                            seg_text = seg.get("text", "")
                            _has_speech = seg_text and "<|nospeech|>" not in seg_text

                            if _has_speech and (seg_end - seg_start) >= 0.5:
                                # 1. VAD子段提取（只取有声部分）
                                if vad_segments:
                                    vad_parts = []
                                    for vs in vad_segments:
                                        vs_s = max(int(vs.get("start", 0) * fs), s_sample)
                                        vs_e = min(int(vs.get("end", 0) * fs), e_sample)
                                        if vs_e > vs_s:
                                            vad_parts.append(audio_full[vs_s:vs_e])
                                    if vad_parts:
                                        seg_vad = np.concatenate(vad_parts) if len(vad_parts) > 1 else vad_parts[0]
                                    else:
                                        seg_vad = audio_full[s_sample:e_sample]
                                else:
                                    seg_vad = audio_full[s_sample:e_sample]

                                seg_len = len(seg_vad)
                                if seg_len > 0:
                                    # 2. 整段打分
                                    try:
                                        full_scores = vp_svc.score_all(seg_vad)
                                        if full_scores:
                                            seg["voiceprint_speaker"] = list(full_scores.keys())[0]
                                            seg["voiceprint_sim"] = round(list(full_scores.values())[0], 4)
                                    except Exception:
                                        pass

                                    # 3. 滑动窗口趋势（段长 >= 1s）
                                    VP_WINDOW_MS = 1000
                                    VP_HOP_MS = 1000
                                    win_samp = int(VP_WINDOW_MS * fs / 1000)
                                    hop_samp = int(VP_HOP_MS * fs / 1000)
                                    if seg_len >= win_samp:
                                        windows = []
                                        for ws in range(0, seg_len - win_samp + 1, hop_samp):
                                            we = ws + win_samp
                                            try:
                                                w_scores = vp_svc.score_all(seg_vad[ws:we])
                                                if w_scores:
                                                    best_spk = list(w_scores.keys())[0]
                                                    windows.append({
                                                        "start_ms": round(ws / fs * 1000),
                                                        "score": round(list(w_scores.values())[0], 4),
                                                        "speaker": best_spk,
                                                    })
                                            except Exception:
                                                pass
                                        if windows:
                                            seg["voiceprint_windows"] = windows
                                            scores_arr = [w["score"] for w in windows]
                                            high_scores = [s for s in scores_arr if s > 0.5]
                                            seg["voiceprint_stats"] = {
                                                "min": round(min(scores_arr), 4),
                                                "max": round(max(scores_arr), 4),
                                                "avg": round(sum(scores_arr) / len(scores_arr), 4),
                                                "user_ratio": round(len(high_scores) / len(scores_arr), 4) if scores_arr else 0,
                                            }
                except ImportError:
                    logger.debug("[AudioAnalysis] voiceprint_service/soundfile 不可用")
                except Exception as e:
                    logger.debug(f"[AudioAnalysis] 声纹匹配异常: {e}")

            # 日志：ASR
            log_parts = [f"[AudioAnalysis] {os.path.basename(audio_path)}"]
            if asr_text:
                log_parts.append(f"ASR=\"{asr_text[:150]}{'...' if len(asr_text) > 150 else ''}\"")
            else:
                log_parts.append("ASR=(无语音)")

            # 日志：VAD
            duration = result.get("duration", 0)
            if not duration and segments:
                duration = max(s.get("end", 0) for s in segments)
            if not duration and vad_segments:
                duration = max(s.get("end", 0) for s in vad_segments)
            if not duration:
                duration = os.path.getsize(audio_path) / 32000 if os.path.exists(audio_path) else 0
            log_parts.append(f"dur={duration:.0f}s")
            if vad_segments:
                log_parts.append(f"VAD={len(vad_segments)}段")
            if silent:
                log_parts.append("silent=True")

            # 日志：场景（只取主要场景名，不要整块 JSON）
            scene_label = ""
            if isinstance(scene, dict):
                primary = scene.get("scene_primary", {})
                scene_label = primary.get("label_cn", "") or primary.get("label", "")
            elif isinstance(scene, str):
                scene_label = scene
            if scene_label:
                log_parts.append(f"场景={scene_label}")

            # 日志：音频事件
            if audio_events:
                top_events = [e.get("label_cn", e.get("label", "?")) for e in audio_events[:5]]
                log_parts.append(f"事件={','.join(top_events)}")

            # 日志：情绪
            emotion_tag = emotion.get("tag") or (emotion.get("dominant_emotion") if isinstance(emotion, dict) else None)
            emotion_prob = emotion.get("probability") or (emotion.get("confidence") if isinstance(emotion, dict) else 0)
            if emotion_tag:
                log_parts.append(f"情绪={emotion_tag}({emotion_prob:.2f})")

            # 日志：声纹
            speaker_name = speaker.get("name", "")
            speaker_sim = speaker.get("similarity", 0)
            spk_threshold = 0.45  # 默认阈值，与 voiceprint_service 一致
            if speaker_name:
                log_parts.append(f"声纹={speaker_name}(sim={speaker_sim:.3f},th={spk_threshold})")

            # 日志：分段详情
            if segments:
                for i, seg in enumerate(segments):
                    seg_text = seg.get("text", "")
                    if seg_text:
                        log_parts.append(f"  段{i}: \"{seg_text[:100]}\"")
                    emotion_s = seg.get("emotion_tag", "")
                    if emotion_s:
                        log_parts.append(f"  ({emotion_s})")

            logger.info(" | ".join(log_parts))

            # 如果 ASR 有文本但之前没有传 text，补写 perception entry
            if asr_text and not any(
                entry.get("type") == "voice"
                for entry in [{}]  # placeholder - we don't check previous entries
            ):
                from datetime import datetime, timezone, timedelta
                enriched_entry = {
                    "type": "voice",
                    "t": datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S"),
                    "hasSpeech": bool(asr_text) and "<|nospeech|>" not in asr_text,
                    "segments": seg_summary(segments) if segments else [],
                    "audio_events": audio_events if audio_events else [],
                    "audio": os.path.relpath(audio_path, get_config().DATA_DIR).replace("\\", "/"),
                }
                if scene and isinstance(scene, dict):
                    primary = scene.get("scene_primary", {})
                    scene_label = primary.get("label_cn", "") or primary.get("label", "")
                    if scene_label:
                        enriched_entry["scene"] = scene_label
                if speaker and isinstance(speaker, dict) and speaker.get("name"):
                    enriched_entry["speaker"] = speaker
                if emotion and isinstance(emotion, dict) and emotion.get("tag"):
                    enriched_entry["emotion"] = emotion
                if asr_text and "<|nospeech|>" not in asr_text:
                    enriched_entry["asr_text"] = asr_text
                append_perception(enriched_entry, auto_type=False)

        except ImportError as e:
            logger.warning(f"[AudioAnalysis] 分析模块未加载: {e}")
        except Exception as e:
            logger.error(f"[AudioAnalysis] 分析异常: {e}", exc_info=True)

    def seg_summary(segments: list) -> list:
        """提取分段摘要（与原始项目格式一致）"""
        summary = []
        for s in segments:
            summary.append({
                "start": s.get("start", 0),
                "end": s.get("end", 0),
                "text": (s.get("text", "") or "")[:200],
                "avg_db": s.get("avg_db", 0),
                "peak_db": s.get("peak_db", 0),
                "db_range": s.get("db_range", 0),
                "zero_crossing_rate": s.get("zero_crossing_rate", 0),
                "spectral_centroid": s.get("spectral_centroid", 0),
                "voice_ratio": s.get("voice_ratio", 0),
                "silence_ratio": s.get("silence_ratio", 0),
                "speech_prob": s.get("speech_prob", 0),
                "emotion_tag": s.get("emotion", "") or s.get("emotion_tag", ""),
                "emotion_prob": s.get("confidence", 0) or s.get("emotion_prob", 0),
                "speaker": s.get("speaker", ""),
                "voiceprint_speaker": s.get("voiceprint_speaker", ""),
                "voiceprint_sim": s.get("voiceprint_sim", 0),
            })
            if s.get("voiceprint_windows"):
                summary[-1]["voiceprint_windows"] = s["voiceprint_windows"]
            if s.get("voiceprint_stats"):
                summary[-1]["voiceprint_stats"] = s["voiceprint_stats"]
        return summary

    threading.Thread(target=_run, name="AudioAnalysis", daemon=True).start()


def _ensure_wav(path: str) -> bool:
    """
    确保音频文件是有效的 WAV 格式。
    Android 可能上传 AAC 等格式，需要转换后才能被 soundfile 读取。
    """
    import wave
    import os
    import subprocess

    try:
        with wave.open(path, "rb") as wf:
            wf.readframes(1)
            return True  # 已经是有效 WAV
    except wave.Error:
        pass  # 非 WAV，需要转换
    except Exception:
        pass

    logger.info(f"[AudioAnalysis] 检测到非 WAV 格式 ({os.path.basename(path)})，正在转换...")

    # 尝试用 ffmpeg 转码
    wav_path = path.rsplit(".", 1)[0] + "_converted.wav"
    ffmpeg_paths = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "ffmpeg.exe"),
        "ffmpeg", "ffmpeg.exe",
    ]
    ffmpeg_cmd = None
    for fp in ffmpeg_paths:
        if fp in ("ffmpeg", "ffmpeg.exe") or os.path.exists(fp):
            ffmpeg_cmd = fp
            break

    if ffmpeg_cmd is None:
        logger.warning("[AudioAnalysis] ffmpeg 未找到，无法转换音频格式")
        return False

    try:
        subprocess.run(
            [ffmpeg_cmd, "-y", "-i", path, "-ar", "16000", "-ac", "1", wav_path],
            capture_output=True, timeout=60
        )
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
            os.replace(wav_path, path)
            logger.info(f"[AudioAnalysis] 转换成功: {os.path.basename(path)}")
            return True
    except FileNotFoundError:
        logger.warning(f"[AudioAnalysis] ffmpeg 未找到 ({ffmpeg_cmd})，无法转换音频格式")
    except subprocess.TimeoutExpired:
        logger.warning("[AudioAnalysis] ffmpeg 转换超时")
    except Exception as e:
        logger.warning(f"[AudioAnalysis] 转换失败: {e}")

    if os.path.exists(wav_path):
        try: os.remove(wav_path)
        except: pass

    return False
