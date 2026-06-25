# -*- coding: utf-8 -*-
"""
语音助手核心服务

处理实时音频流，执行 VAD 切分、声纹滑动窗口分析、
ASR 转录、停止决策。

使用方式:
    svc = get_voice_assistant_service()
    svc.on_event(lambda event, data: ...)  # 注册回调
    svc.start(source="android")
    svc.feed_audio(pcm_bytes)  # 持续调用
    svc.stop()  # 手动停止
"""

import os
import time
import logging
import threading
import tempfile
import wave
from collections import deque
from typing import Optional, Callable, Dict, Any, List, Deque

import numpy as np

logger = logging.getLogger(__name__)


class VoiceAssistantService:
    """
    语音助手核心服务

    处理实时音频流，执行 VAD 切分、声纹滑动窗口分析、
    ASR 转录、停止决策。

    架构说明:
    1. feed_audio() 接收 Android VIS 实时 PCM 流 (16kHz, 16-bit, mono)
    2. 能量 VAD 检测语音/静音边界，积累语音段落到 _current_segment
    3. 声纹滑动窗口每 500ms 分析一次，对最近 8000 样本打分
    4. 停止条件: 声纹连续 2s <= 0.5 或静音持续 3s
    5. 段落完成时根据声纹分数决定是否送入 ASR
    6. 通过事件回调通知 WS 处理层，不直接发送 WebSocket 消息
    """

    # --- 音频参数 ---
    SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    BITS_PER_SAMPLE: int = 16

    # --- 能量 VAD (参考 VoiceRecorder.kt) ---
    RMS_THRESHOLD: float = 5.0       # RMS 能量阈值，低于此值视为静音
    MIN_SPEECH_MS: int = 500         # 最短语音段落 (ms)，不足则丢弃
    SILENCE_TIMEOUT_MS: int = 3000   # 静音超时 (ms)，触发 stop_recording

    # --- 声纹滑动窗口 ---
    VOICEPRINT_WINDOW_MS: int = 1000  # 滑动窗口粒度 (ms) = 16000 样本 (原500ms太短导致分数不稳定)
    VOICEPRINT_HISTORY_MS: int = 3000 # 声纹历史窗口 (ms) = 3 个窗口
    VOICEPRINT_THRESHOLD: float = 0.5 # 声纹低分阈值，<=0.5 视为非用户

    # --- ASR ---
    MIN_SEGMENT_MS: int = 500  # 最短 ASR 段落 (ms)

    def __init__(self):
        # 运行状态
        self._running: bool = False
        self._source: str = ""
        self._start_time: float = 0.0   # start() 调用时间戳 (ms)

        # PCM 缓冲区 (累积所有音频，用于声纹滑动窗口)
        self._buffer: bytearray = bytearray()

        # VAD 状态
        self._current_segment: bytearray = bytearray()  # 当前语音段落累积
        self._speaking: bool = False                     # 是否正在说话
        self._speech_start_ms: float = 0.0              # 当前段落的开始时间 (ms)
        self._last_speech_ms: float = 0.0               # 最近一次语音活动时间 (ms)
        self._silence_start_ms: float = 0.0             # 静音开始的绝对时间 (ms)
        self._segment_id: int = 0                        # 段落计数器

        # 声纹滑动窗口状态
        self._vp_scores: Deque[float] = deque(maxlen=3)  # 最近 3 个声纹分数 (3s @ 1000ms窗)
        self._last_vp_window_bytes: int = 0              # 上次声纹窗口时的字节偏移量
        self._segment_vp_scores: List[float] = []        # 当前段落的声纹分数列表

        # 已完成的段落记录（用于最终结果汇总）
        self._completed_segments: List[Dict[str, Any]] = []

        # 服务引用 (懒加载)
        self._voiceprint_service: Optional[Any] = None
        self._vp_initialized: bool = False
        self._has_registered_speakers: bool = False

        # 事件回调
        self._callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

        # 线程安全 (feed_audio 可能被多线程调用)
        self._lock: threading.Lock = threading.Lock()

        logger.info("[VoiceAssistant] 服务实例已创建")

    # ========== 事件回调系统 ==========

    def on_event(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        注册服务事件回调。

        Args:
            callback: (event_type, data) -> None
                支持的事件类型: started, vad_state, voiceprint_score,
                              partial, stop_recording, result, error
        """
        self._callback = callback

    def _fire(self, event_type: str, data: Dict[str, Any]) -> None:
        """触发事件回调 (非阻塞)"""
        if self._callback is not None:
            try:
                self._callback(event_type, data)
            except Exception as e:
                logger.error(f"[VoiceAssistant] 回调执行失败 event={event_type}: {e}")

    # ========== 生命周期管理 ==========

    def start(self, source: str = "android") -> None:
        """
        启动语音助手服务。

        Args:
            source: 音频来源, "android" 或 "web"
        """
        if self._running:
            logger.warning("[VoiceAssistant] 已在运行中")
            return

        # 重置所有状态
        self._reset_state()
        self._running = True
        self._source = source
        self._start_time = time.time() * 1000

        # 懒加载声纹服务
        self._lazy_init_voiceprint()

        logger.info(f"[VoiceAssistant] 已启动, source={source}")
        self._fire("started", {"source": source})

    def stop(self) -> None:
        """
        停止语音助手服务。

        触发行为:
        1. 如果正在说话，先完成当前段落 (finalize)
        2. 发出 stop_recording 事件
        3. 发出 result 事件汇总本轮数据
        """
        if not self._running:
            return

        # 先完成当前段落
        self._finalize_segment()

        self._running = False
        duration_ms = int(time.time() * 1000 - self._start_time)

        logger.info(f"[VoiceAssistant] 已停止, 持续 {duration_ms}ms")

        self._fire("result", {
            "text": "",
            "duration_ms": duration_ms,
            "segments": self._completed_segments,
            "voiceprint_log": list(self._vp_scores),
            "sound_events": self._classify_sound_events(),
        })

    def get_status(self) -> Dict[str, Any]:
        """获取服务当前状态"""
        buffer_ms = 0
        if self._running and len(self._buffer) > 0:
            bytes_per_ms = self.SAMPLE_RATE * self.BITS_PER_SAMPLE // 8 // 1000
            buffer_ms = int(len(self._buffer) / bytes_per_ms) if bytes_per_ms > 0 else 0

        return {
            "running": self._running,
            "source": self._source,
            "speaking": self._speaking,
            "buffer_ms": buffer_ms,
            "segment_id": self._segment_id,
            "voiceprint_history": list(self._vp_scores),
            "has_speakers": self._has_registered_speakers,
        }

    # ========== 音频输入 ==========

    def feed_audio(self, pcm_bytes: bytes) -> None:
        """
        输入实时 PCM 音频数据。

        每帧处理流程:
        1. 追加到主缓冲区 (_buffer)，用于声纹滑动窗口
        2. 每 500ms 执行一次声纹滑动窗口分析
        3. 能量 VAD 检测语音/静音边界
        4. 检查停止条件

        Args:
            pcm_bytes: PCM 音频数据 (16kHz, 16-bit, mono, little-endian)
        """
        if not self._running or not pcm_bytes:
            return

        with self._lock:
            # 追加到主缓冲区
            self._buffer.extend(pcm_bytes)

            # 限制主缓冲区大小防止内存溢出 (保留最近 5s)
            max_buffer_bytes = self.SAMPLE_RATE * 5 * 2  # 5s * 2 bytes/sample
            if len(self._buffer) > max_buffer_bytes:
                trim = len(self._buffer) - max_buffer_bytes
                self._buffer = self._buffer[trim:]

            now_ms = time.time() * 1000

            # --- 声纹滑动窗口 (每 500ms) ---
            self._run_voiceprint_window()

            # --- 能量 VAD ---
            rms = self._calculate_rms(pcm_bytes)

            if rms > self.RMS_THRESHOLD:
                # === 检测到语音 ===
                if not self._speaking:
                    self._speaking = True
                    self._speech_start_ms = now_ms
                    self._current_segment = bytearray()
                    self._segment_vp_scores = []
                    logger.debug(f"[VoiceAssistant] 语音开始 (rms={rms:.1f})")
                    self._fire("vad_state", {"state": "speech"})

                # 语音数据追加到当前段落
                self._current_segment.extend(pcm_bytes)
                self._last_speech_ms = now_ms
                self._silence_start_ms = 0.0  # 重置静音计时器

            else:
                # === 检测到静音 ===
                if self._speaking:
                    # 静音也积累到段落尾部 (保留上下文)
                    self._current_segment.extend(pcm_bytes)

                    if self._silence_start_ms == 0.0:
                        self._silence_start_ms = now_ms
                        logger.debug(f"[VoiceAssistant] 静音开始")

                    silence_duration = now_ms - self._silence_start_ms

                    if silence_duration >= self.SILENCE_TIMEOUT_MS:
                        # 静音超时 -> 停止
                        logger.info(f"[VoiceAssistant] 静音超时 ({silence_duration:.0f}ms >= {self.SILENCE_TIMEOUT_MS}ms)")
                        self._finalize_segment()
                        self._fire("stop_recording", {"cause": "silence"})
                        self.stop()

            # --- 声纹驱动的停止决策 (3 个连续 1s 窗口均 <=0.5 则停止) ---
            _vp_maxlen = self._vp_scores.maxlen or 3
            if self._has_registered_speakers and len(self._vp_scores) >= _vp_maxlen:
                # 检查最近 N 个分数是否全部 <= 阈值
                all_low = all(s <= self.VOICEPRINT_THRESHOLD for s in self._vp_scores)
                if all_low and self._speaking:
                    logger.info(f"[VoiceAssistant] 声纹连续低分 {list(self._vp_scores)}, 判定非用户说话")
                    self._finalize_segment()
                    self._fire("stop_recording", {"cause": "voiceprint"})
                    self.stop()

    # ========== 能量 VAD ==========

    @staticmethod
    def _calculate_rms(pcm_bytes: bytes) -> float:
        """
        计算 PCM 数据的 RMS 能量值。

        与 VoiceRecorder.kt 的算法一致:
            rms = sqrt(sum(x^2) / n)

        Args:
            pcm_bytes: 原始 PCM int16 字节数据

        Returns:
            RMS 能量值
        """
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        # 使用 float64 避免溢出
        sum_sq = np.sum(samples.astype(np.float64) ** 2)
        return float(np.sqrt(sum_sq / len(samples)))

    # ========== 声纹滑动窗口 ==========

    def _lazy_init_voiceprint(self) -> None:
        """懒加载声纹服务并检查是否有注册说话人"""
        if self._vp_initialized:
            return
        try:
            # KMP_DUPLICATE_LIB_OK 由 voiceprint_service 内部处理
            from services.voiceprint_service import get_voiceprint_service
            svc = get_voiceprint_service()
            self._voiceprint_service = svc
            # 用 get_speaker_count 判断（不依赖模型就绪，模型会在 score_all 时懒加载）
            speaker_count = svc.get_speaker_count()
            self._has_registered_speakers = speaker_count > 0
            logger.info(f"[VoiceAssistant] 声纹服务初始化完成, 注册说话人: {speaker_count}")
        except Exception as e:
            logger.warning(f"[VoiceAssistant] 声纹服务初始化失败, 仅使用静音停止: {e}")
            self._voiceprint_service = None
            self._has_registered_speakers = False
        self._vp_initialized = True

    def _run_voiceprint_window(self) -> None:
        """
        执行声纹滑动窗口分析 (每 500ms 音频数据)。

        基于收到的字节数进行门控，每累积 8000 个 int16 样本
        (500ms @ 16kHz) 执行一次声纹分析。用字节计数而非
        墙钟时间，确保测试环境下行为确定且可靠。
        """
        if not self._has_registered_speakers:
            return

        # 字节计数门控: 每累积 500ms 数据执行一次
        window_samples = self.SAMPLE_RATE * self.VOICEPRINT_WINDOW_MS // 1000  # = 8000
        window_bytes = window_samples * 2  # int16 = 2 bytes
        if len(self._buffer) - self._last_vp_window_bytes < window_bytes:
            return
        self._last_vp_window_bytes = len(self._buffer)

        needed_bytes = window_bytes

        if len(self._buffer) < needed_bytes:
            return  # 缓冲区数据不足

        # 取主缓冲区最后 window_samples 个样本
        pcm_slice = bytes(self._buffer[-needed_bytes:])
        int16_samples = np.frombuffer(pcm_slice, dtype=np.int16)
        float32_samples = int16_samples.astype(np.float32) / 32768.0

        svc = self._get_voiceprint_service()
        if svc is None:
            return

        try:
            scores = svc.score_all(float32_samples)
            if scores:
                max_score = max(scores.values())
                self._vp_scores.append(max_score)
                self._segment_vp_scores.append(max_score)

                self._fire("voiceprint_score", {
                    "score": max_score,
                    "window_ms": self.VOICEPRINT_WINDOW_MS,
                    "all_scores": scores,
                })
        except Exception as e:
            logger.warning(f"[VoiceAssistant] 声纹分析失败: {e}")

    def _get_voiceprint_service(self) -> Optional[Any]:
        """获取声纹服务实例 (线程安全)"""
        if self._voiceprint_service is None and not self._vp_initialized:
            self._lazy_init_voiceprint()
        return self._voiceprint_service

    # ========== 段落完成与 ASR ==========

    def _finalize_segment(self) -> None:
        """
        完成当前语音段落。

        流程:
        1. 检查段落长度是否达标 (>= MIN_SEGMENT_MS)
        2. 计算段落的平均声纹分数
        3. 如果声纹分数 > 阈值 (或无注册说话人)，送入 ASR
        4. 发出 partial 事件
        """
        if not self._current_segment or len(self._current_segment) == 0:
            return

        pcm_data = bytes(self._current_segment)
        bytes_per_ms = self.SAMPLE_RATE * self.BITS_PER_SAMPLE // 8 // 1000
        duration_ms = int(len(pcm_data) / bytes_per_ms) if bytes_per_ms > 0 else 0

        if duration_ms < self.MIN_SEGMENT_MS:
            logger.debug(f"[VoiceAssistant] 段落太短 ({duration_ms}ms), 丢弃")
            self._current_segment = bytearray()
            self._segment_vp_scores = []
            return

        # 计算段落平均声纹分数
        avg_vp = 0.0
        if self._segment_vp_scores:
            avg_vp = sum(self._segment_vp_scores) / len(self._segment_vp_scores)

        segment_start = int(self._speech_start_ms - self._start_time)

        # 决策: 用户语音 (分数高) 或没有注册声纹 -> 执行 ASR
        text = ""
        should_transcribe = avg_vp > self.VOICEPRINT_THRESHOLD or not self._has_registered_speakers
        if should_transcribe:
            text = self._transcribe_audio(pcm_data)
            logger.info(f"[VoiceAssistant] ASR 结果: {text[:80]}")
        else:
            logger.debug(f"[VoiceAssistant] 跳过 ASR (avg_vp={avg_vp:.3f} <= {self.VOICEPRINT_THRESHOLD})")

        self._segment_id += 1

        # 判断说话人身份
        speaker_label = "贺吸呼" if avg_vp > self.VOICEPRINT_THRESHOLD else "unknown"

        segment_info = {
            "segment_id": self._segment_id,
            "start_ms": segment_start,
            "end_ms": segment_start + duration_ms,
            "duration_ms": duration_ms,
            "voiceprint_scores": list(self._segment_vp_scores),
            "avg_voiceprint": round(avg_vp, 4),
            "speaker": speaker_label,
            "text": text,
        }

        # 记录段落到已完成列表（用于最终 result 汇总）
        segment_record = {
            "start_ms": segment_start,
            "end_ms": segment_start + duration_ms,
            "speaker": speaker_label,
            "voiceprint_score": round(avg_vp, 4),
            "text": text,
        }
        self._completed_segments.append(segment_record)

        logger.info(f"[VoiceAssistant] 段落 {self._segment_id}: {duration_ms}ms, vp={avg_vp:.3f}, "
                     f"text='{text[:60] if text else '(空)'}'")

        self._fire("partial", segment_info)

        # 重置段落状态
        self._current_segment = bytearray()
        self._segment_vp_scores = []

    def _transcribe_audio(self, pcm_data: bytes) -> str:
        """
        使用阿里云 ASR 转录音频数据。

        将 PCM 数据写入临时 WAV 文件后调用 AliyunASRFileService。
        如果 ASR 不可用，返回空字符串。

        Args:
            pcm_data: 原始 PCM int16 数据

        Returns:
            识别文本，失败返回空字符串
        """
        try:
            from services.aliyun_asr_service import AliyunASRFileService

            # 写入临时 WAV 文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name
                self._write_wav(temp_path, pcm_data)

            try:
                asr = AliyunASRFileService()
                text = asr.transcribe_file(temp_path)
                return text
            except Exception as e:
                logger.warning(f"[VoiceAssistant] ASR 调用失败: {e}")
                return ""
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        except ImportError:
            logger.warning("[VoiceAssistant] aliyun_asr_service 不可用, ASR 跳过")
            return ""
        except Exception as e:
            logger.warning(f"[VoiceAssistant] ASR 异常: {e}")
            return ""

    @staticmethod
    def _write_wav(path: str, pcm_data: bytes, sample_rate: int = 16000) -> None:
        """
        将 PCM int16 数据写入 WAV 文件。

        Args:
            path: 输出文件路径
            pcm_data: PCM int16 字节数据 (little-endian)
            sample_rate: 采样率 (Hz)
        """
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)       # mono
            wf.setsampwidth(2)       # 16-bit = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)

    # ========== 声音事件分类 ==========

    def _classify_sound_events(self) -> List[Dict[str, Any]]:
        """
        对整段音频做基本的声音事件分类。

        先用能量 RMS 做粗略的 speech/silence 判断，
        再尝试加载 multimodal_audio_manager 获取更精确的 PANNs 标签。
        如果 multimodal 不可用则返回能量估计结果作为兜底。

        Returns:
            [{"start_ms": int, "end_ms": int, "label": str, "confidence": float}, ...]
        """
        events = []
        if len(self._buffer) == 0:
            return events

        # 计算整段音频的总体能量
        samples = np.frombuffer(bytes(self._buffer), dtype=np.int16)
        total_ms = int(len(self._buffer) / (self.SAMPLE_RATE * 2 / 1000))  # bytes -> ms

        if len(samples) > 0:
            avg_rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
            if avg_rms > self.RMS_THRESHOLD * 2:
                events.append({
                    "start_ms": 0,
                    "end_ms": total_ms,
                    "label": "speech",
                    "confidence": 0.7,
                })
            else:
                events.append({
                    "start_ms": 0,
                    "end_ms": total_ms,
                    "label": "silence",
                    "confidence": 0.9,
                })

        # 尝试使用 multimodal_audio_manager 增强标签
        try:
            from services.multimodal_audio_manager import get_multimodal_audio_manager
            manager = get_multimodal_audio_manager()
            if manager._loaded and hasattr(manager, '_scene_analyzer') and manager._scene_analyzer is not None:
                # 需要先将 PCM 写入临时 WAV 文件供分析
                import tempfile as _tf
                with _tf.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name
                try:
                    self._write_wav(tmp_path, bytes(self._buffer))
                    scene_result = manager.analyze_scene_only(tmp_path)
                    if scene_result and scene_result.get("success"):
                        # 用 audio_events 替换基本标签
                        aed = scene_result.get("audio_events", [])
                        if aed:
                            events = aed
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
        except Exception:
            pass  # multimodal 不可用时使用能量估计

        return events

    # ========== 内部状态管理 ==========

    def _reset_state(self) -> None:
        """重置所有内部状态 (start 时调用)"""
        self._buffer = bytearray()
        self._current_segment = bytearray()
        self._speaking = False
        self._speech_start_ms = 0.0
        self._last_speech_ms = 0.0
        self._silence_start_ms = 0.0
        self._segment_id = 0
        self._start_time = 0.0

        self._vp_scores.clear()
        self._last_vp_window_bytes = 0
        self._segment_vp_scores.clear()
        self._completed_segments = []


# ========== 单例 ==========

_instance: Optional[VoiceAssistantService] = None
_instance_lock = threading.Lock()


def get_voice_assistant_service() -> VoiceAssistantService:
    """
    获取全局 VoiceAssistantService 单例。

    线程安全的懒加载单例模式。

    Returns:
        VoiceAssistantService 实例
    """
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = VoiceAssistantService()
    return _instance
