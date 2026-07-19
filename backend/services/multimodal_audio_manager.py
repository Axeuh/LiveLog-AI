"""
多模态音频分析管理器

直接使用 multimodal-demo 的 AudioProcessor 管线。
提供单例包装，供 backend 路由层调用。

能力:
- SenseVoice ASR (中文/英文/日文等多语言)
- 情绪识别 (SenseVoice emotion token + 置信度校准)
- 环境场景分析 (PANNs - 需手动启用)
- 音频事件检测 (PANNs AED)
- 呼吸/叹气检测
- 说话人日志 (MFCC 聚类)

输出格式:
    严格遵循 multimodal-demo/audio_processor.py 的 process() 输出。
    {
        "success": bool,
        "duration": float,
        "duration_str": str,
        "segments": [...],
        "emotion_summary": {...},
        "emotion_distribution": [...],
        "event_summary": {...},
        "dominant_emotion": str,
        "dominant_emotion_cn": str,
        ...
    }
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# ─── 导入 multimodal-demo 模块 ────────────────────────────
_MULTIMODAL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'multimodal-demo')
)
if _MULTIMODAL_DIR not in sys.path:
    sys.path.insert(0, _MULTIMODAL_DIR)


# ─── 设备检测 ──────────────────────────────────────────
import torch

def _detect_device() -> str:
    if torch.cuda.is_available():
        logger.info(f"[Multimodal] 使用 CUDA: {torch.cuda.get_device_name(0)}")
        return "cuda:0"
    logger.info("[Multimodal] CUDA 不可用，使用 CPU")
    return "cpu"


_DEVICE = _detect_device()


# ─── 单例 ──────────────────────────────────────────────
_INSTANCE = None
_LOCK = threading.Lock()


class MultimodalAudioManager:
    """
    多模态音频分析管理器 (单例)

    封装 multimodal-demo 的 AudioProcessor 并编排其依赖。
    延迟加载所有模型，在 lifespan 中预加载。
    """

    def __init__(self):
        self._processor = None          # AudioProcessor (SenseVoice + 编排)
        self._scene_analyzer = None     # SceneAnalyzer (PANNs)
        self._vad_processor = None      # VADProcessor (Silero VAD)
        self._emotion_model = None      # emotion2vec+
        self._speaker_diarizer = None   # SpeakerDiarizer (MFCC 聚类)
        self._device = _DEVICE
        self._loaded = False
        self._load_error: Optional[str] = None

    # ── 模型加载 ──────────────────────────────────────
    def load_models(self):
        """预加载所有模型（在 lifespan 中调用，线程安全）。"""
        if self._loaded:
            return
        t0 = time.time()
        logger.info("[Multimodal] 开始加载模型...")

        # ─── 修复 speechbrain LazyModule 的 cascading import 异常 ────────
        # speechbrain 的 LazyModule 在 __getattr__ 中触发 import。
        # 当 inspect.stack() 通过 hasattr(module, '__file__') 检查时 ->
        #   LazyModule.__getattr__('__file__') ->
        #   ensure_module() -> inspect.getframeinfo() (递归!)
        # 补丁：对 __file__ 短路返回，避免触发 import 和递归
        try:
            from speechbrain.utils.importutils import LazyModule
            original_getattr = LazyModule.__getattr__
            def _safe_getattr(self, attr):
                if attr == '__file__':
                    raise AttributeError(f"LazyModule({self.target}) not loaded")
                try:
                    return original_getattr(self, attr)
                except ImportError:
                    raise AttributeError(
                        f"Lazy import of {self.target} failed, "
                        f"suppressed for hasattr compatibility"
                    )
            LazyModule.__getattr__ = _safe_getattr
            logger.info("[Multimodal] speechbrain LazyModule 已打补丁（防止 cascading import 崩溃）")
        except ImportError:
            pass  # speechbrain not installed, no fix needed

        try:
            # 1. VAD
            self._load_vad()
            # 2. PANNs 场景分析器
            self._load_scene_analyzer()
            # 3. emotion2vec+
            self._load_emotion_model()
            # 4. 说话人日志 (MFCC 聚类，零加载时间)
            self._load_speaker_diarizer()
            # 5. AudioProcessor (SenseVoice + PANNs + 编排)
            self._load_audio_processor()

            self._loaded = True
            logger.info(f"[Multimodal] 全部模型加载完成 ({time.time()-t0:.1f}s)")
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"[Multimodal] 模型加载失败: {e}")

    def _load_vad(self):
        try:
            from vad_processor import VADProcessor
            self._vad_processor = VADProcessor(device=self._device)
            self._vad_processor._load_model()
            logger.info("[Multimodal] Silero VAD 加载完成")
        except Exception as e:
            logger.warning(f"[Multimodal] VAD 加载失败（不影响基础 ASR）: {e}")
            self._vad_processor = None

    def _load_emotion_model(self):
        try:
            from funasr import AutoModel
            self._emotion_model = AutoModel(
                model="iic/emotion2vec_plus_base",
                disable_update=True,
                device=self._device,
            )
            logger.info("[Multimodal] emotion2vec+ 加载完成")
        except Exception as e:
            logger.warning(f"[Multimodal] emotion2vec+ 加载失败: {e}")
            self._emotion_model = None

    def _load_scene_analyzer(self):
        """加载 PANNs 场景/事件分析器。"""
        try:
            from sound_scene import SceneAnalyzer
            self._scene_analyzer = SceneAnalyzer(device=self._device)
            self._scene_analyzer._load_model()
            logger.info("[Multimodal] PANNs 场景分析器加载完成")
        except Exception as e:
            logger.warning(f"[Multimodal] PANNs 加载失败（不影响 ASR）: {e}")
            self._scene_analyzer = None

    def _load_speaker_diarizer(self):
        """加载说话人日志处理器 (MFCC + 聚类，零模型下载)。"""
        try:
            from speaker_diarization import SpeakerDiarizer
            self._speaker_diarizer = SpeakerDiarizer(device=self._device)
            logger.info("[Multimodal] SpeakerDiarizer 已就绪 (MFCC + 聚类)")
        except Exception as e:
            logger.warning(f"[Multimodal] SpeakerDiarizer 加载失败: {e}")
            self._speaker_diarizer = None

    def _load_audio_processor(self):
        from audio_processor import AudioProcessor
        self._processor = AudioProcessor(
            device=self._device,
            scene_analyzer=self._scene_analyzer,
            speaker_diarizer=self._speaker_diarizer,
            source_separator=None,
            tracks_output_dir=None,
            vad_processor=self._vad_processor,
            emotion_model=self._emotion_model,
        )
        self._processor._load_model()
        logger.info("[Multimodal] SenseVoice ASR + PANNs 加载完成")

    # ── 核心 API ──────────────────────────────────────
    def analyze(self, audio_path: str,
                enable_vad: bool = True) -> Dict[str, Any]:
        """
        音频全分析。

        Args:
            audio_path: 16kHz 单声道 WAV 文件路径
            enable_vad: 是否使用 VAD 分段

        Returns:
            完整分析 JSON (同 multimodal-demo output format)
        """
        if self._processor is None:
            self.load_models()
        if self._processor is None:
            return {"success": False, "error": self._load_error or "模型加载失败"}

        try:
            result = self._processor.process(audio_path)
            # 补充顶层 text 字段（从 segments 拼接）
            if result.get("success") and "text" not in result:
                texts = [s["text"] for s in result.get("segments", []) if s.get("text")]
                result["text"] = "".join(texts)
            return result
        except Exception as e:
            logger.exception(f"[Multimodal] 分析失败")  # 带 traceback
            return {"success": False, "error": str(e) or type(e).__name__}

    def analyze_scene_only(self, audio_path: str) -> Dict[str, Any]:
        """
        仅 PANNs 场景 + 音频事件检测，不跑 SenseVoice ASR。

        比全分析快 ~3-5x（~0.3s vs ~1-2s），
        适合 VAD 判定无人声时只采集环境声信息。

        Args:
            audio_path: 16kHz 单声道 WAV 文件路径

        Returns:
            {
                "success": bool,
                "duration": float,
                "segments": [],        # 无 ASR 所以空
                "text": "",
                "scene": {...},         # PANNs 场景
                "audio_events": [...],  # PANNs 音频事件
            }
        """
        import soundfile as sf

        result = {
            "success": True,
            "segments": [],
            "text": "",
        }

        # 时长
        try:
            info = sf.info(audio_path)
            duration = round(info.duration, 1)
            result["duration"] = duration
            result["duration_str"] = f"{int(duration // 60)}分{int(duration % 60)}秒"
        except Exception:
            pass

        # PANNs 场景 + 事件
        if self._scene_analyzer is not None:
            try:
                scene_result = self._scene_analyzer.classify_scene(audio_path, top_k=5)
                if scene_result:
                    result["scene"] = scene_result
                logger.debug("[Multimodal] 仅场景分析完成")
            except Exception as e:
                logger.warning(f"[Multimodal] 仅场景分析失败: {e}")

            try:
                aed_result = self._scene_analyzer.classify_segments(
                    audio_path, segment_duration=2.0, top_k=5
                )
                if aed_result:
                    result["audio_events"] = aed_result
                logger.debug("[Multimodal] 仅事件检测完成")
            except Exception as e:
                logger.warning(f"[Multimodal] 仅事件检测失败: {e}")

        return result

    def transcribe(self, audio_path: str) -> str:
        """
        纯 ASR，返回文字。

        Args:
            audio_path: 音频文件路径

        Returns:
            识别文本（失败返回空串）
        """
        result = self.analyze(audio_path)
        if not result.get("success"):
            return ""
        texts = [s["text"] for s in result.get("segments", []) if s.get("text")]
        return "".join(texts)

    def unload_models(self):
        """释放模型。"""
        with _LOCK:
            self._processor = None
            self._scene_analyzer = None
            self._vad_processor = None
            self._emotion_model = None
            self._speaker_diarizer = None
            self._loaded = False
            import gc; gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("[Multimodal] 模型已释放")


def get_multimodal_audio_manager() -> MultimodalAudioManager:
    """获取管理器单例。"""
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = MultimodalAudioManager()
    return _INSTANCE
