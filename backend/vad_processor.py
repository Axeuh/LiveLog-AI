"""
语音活动检测 (VAD) 模块
使用 Silero VAD 检测语音片段，用于 SenseVoice 预分段。
"""
import os
import logging
import threading
import numpy as np
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VADProcessor:
    """Silero VAD 语音活动检测器。"""

    def __init__(self, device: str = "cuda:0"):
        self._model = None
        self.device = device
        self._lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:  # double-check
                return
            logger.info("正在加载 Silero VAD 模型...")
            from silero_vad import load_silero_vad
            self._model = load_silero_vad()
            logger.info("Silero VAD 模型加载完成！")

    def detect_segments(
        self,
        audio_path: str,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 200,
        min_silence_duration_ms: int = 300,
    ) -> List[Dict]:
        """
        检测语音片段。

        Args:
            audio_path: 16kHz 单声道 WAV 路径
            threshold: VAD 阈值 (0-1)
            min_speech_duration_ms: 最小语音段时长(ms)，短于此的丢弃
            min_silence_duration_ms: 最小静音间隔(ms)，短于此的合并

        Returns:
            [{start: float(秒), end: float(秒)}, ...]
        """
        self._load_model()
        import soundfile as sf
        from silero_vad import get_speech_timestamps

        wav, sr = sf.read(audio_path)
        if wav.ndim > 1:
            wav = wav.mean(axis=1)

        # 确保 16kHz
        if sr != 16000:
            import librosa
            wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)
            sr = 16000

        # 加锁防止并发请求踩踏 Silero VAD 模型内部 RNN state
        with self._lock:
            speech_ts = get_speech_timestamps(
                wav,
                self._model,
                threshold=threshold,
                min_speech_duration_ms=min_speech_duration_ms,
                min_silence_duration_ms=min_silence_duration_ms,
                return_seconds=True,
            )

        segments = []
        for ts in speech_ts:
            segments.append({
                "start": round(ts["start"], 2),
                "end": round(ts["end"], 2),
            })

        n = len(segments)
        if n == 0:
            logger.warning("VAD 未检测到语音段，使用整段音频")
            duration = len(wav) / sr
            segments.append({"start": 0.0, "end": round(duration, 2)})
        else:
            logger.info(f"VAD 检测到 {n} 个语音段")

        # 合并太近的段
        merged = self._merge_nearby(segments)
        if len(merged) != n:
            logger.info(f"VAD 合并后: {len(merged)} 段")
        return merged

    def _merge_nearby(self, segments: List[Dict], gap: float = 0.3) -> List[Dict]:
        """合并间隔小于 gap 秒的相邻段。"""
        if len(segments) <= 1:
            return segments
        merged = [segments[0]]
        for seg in segments[1:]:
            if seg["start"] - merged[-1]["end"] < gap:
                merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
            else:
                merged.append(seg)
        return merged


def cut_audio_segment(audio_path: str, start: float, end: float) -> np.ndarray:
    """从音频文件中裁剪一段，返回 16kHz numpy 数组。"""
    import soundfile as sf
    import librosa

    wav, sr = sf.read(audio_path)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)

    if sr != 16000:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)
        sr = 16000

    start_sample = int(start * sr)
    end_sample = int(end * sr)
    end_sample = min(end_sample, len(wav))

    return wav[start_sample:end_sample].astype(np.float32)
