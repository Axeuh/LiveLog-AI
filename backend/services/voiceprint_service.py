"""
声纹注册/识别服务

基于 funasr ERes2NetV2 提取说话人嵌入向量，
通过余弦相似度进行声纹比对。

使用方式:
    from services.voiceprint_service import get_voiceprint_service
    svc = get_voiceprint_service()
    svc.enroll("张三", "/path/to/audio.wav")
    result = svc.identify("/path/to/test.wav")

数据存储:
    backend/data/voiceprints.json — 注册声纹库

依赖:
    pip install funasr modelscope
"""

import os
import json
import time
import uuid
import logging
import threading
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))

# 数据目录 — 从统一配置读取
from config.config import get_config
_cfg_vp = get_config()
_DATA_DIR = _cfg_vp.DATA_DIR
_VOICEPRINTS_PATH = _cfg_vp.VOICEPRINTS_PATH
_VOICE_AUDIO_DIR = os.path.join(os.path.dirname(_VOICEPRINTS_PATH), "voice_audio")

# 余弦相似度阈值
VERIFY_THRESHOLD = 0.55
IDENTIFY_THRESHOLD = 0.45

# 嵌入维度（ERes2NetV2 输出固定 192 维）
EMBEDDING_DIM = 192


class VoiceprintService:
    """声纹注册/识别服务 — 线程安全，延迟加载模型（基于 ERes2NetV2）。"""

    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self._registry_lock = threading.Lock()
        self._device = "cpu"
        self._loaded = False
        self._load_error: Optional[str] = None
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._load_registry()

    # ─── 属性 ────────────────────────────────────────────

    @property
    def _ready(self) -> bool:
        return self._loaded and self._model is not None

    # ─── 模型加载 ────────────────────────────────────────

    def is_ready(self) -> bool:
        return self._ready

    def _load_model(self) -> bool:
        """延迟加载 ERes2NetV2 模型。"""
        if self._loaded and self._model is not None:
            return True
        with self._model_lock:
            if self._loaded and self._model is not None:
                return True
            try:
                import torch
                self._device = "cuda:0" if torch.cuda.is_available() else "cpu"
                logger.info(f"[Voiceprint] 加载 ERes2NetV2 模型 (device={self._device})...")

                from funasr import AutoModel
                self._model = AutoModel(
                    model="iic/speech_eres2netv2_sv_zh-cn_16k-common",
                    device=self._device,
                    disable_update=True,
                )
                self._loaded = True
                logger.info("[Voiceprint] ERes2NetV2 模型加载完成")
                return True

            except ImportError:
                logger.warning("[Voiceprint] funasr 未安装，声纹功能不可用。pip install funasr")
                self._load_error = "funasr not installed"
                return False
            except Exception as e:
                logger.warning(f"[Voiceprint] 模型加载失败: {e}")
                self._load_error = str(e)
                return False

    # ─── 嵌入向量提取 ────────────────────────────────────

    def extract_embedding(self, audio_data) -> Optional[np.ndarray]:
        """
        从音频数据提取说话人嵌入向量。

        Args:
            audio_data: 文件路径(str) 或 numpy 数组 (16kHz float32)

        Returns:
            192 维嵌入向量 (np.ndarray)，失败返回 None
        """
        if not self._load_model():
            return None
        try:
            result = self._model.generate(input=audio_data)
            # 解析返回结构
            if isinstance(result, list) and len(result) > 0:
                if isinstance(result[0], dict):
                    emb = result[0].get("spk_embedding")
                else:
                    emb = result[0]
            elif isinstance(result, dict):
                emb = result.get("spk_embedding")
            else:
                logger.warning(f"[Voiceprint] 无法解析模型输出: {type(result)}")
                return None

            if emb is None:
                logger.warning("[Voiceprint] 模型未返回 spk_embedding")
                return None

            if hasattr(emb, "cpu"):
                emb = emb.cpu().numpy()
            emb = np.asarray(emb).flatten()
            return emb

        except Exception as e:
            logger.warning(f"[Voiceprint] 嵌入向量提取失败: {e}")
            return None

    # ─── 余弦相似度 ──────────────────────────────────────

    @staticmethod
    def compute_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """计算两个嵌入向量的余弦相似度。"""
        a = emb_a.flatten()
        b = emb_b.flatten()
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-8 or norm_b < 1e-8:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    # ─── 声纹注册 ────────────────────────────────────────

    def enroll(self, name: str, audio_path: str, remark: str = "") -> Optional[Dict[str, Any]]:
        """
        注册声纹。

        Args:
            name: 说话人姓名/标识
            audio_path: 音频文件路径（建议 3-10 秒清晰语音）
            remark: 备注（如录音环境等）

        Returns:
            {"speaker_id": str, "name": str, "remark": str, "embedding_dim": int, "created_at": str}
             失败返回 None
        """
        embedding = self.extract_embedding(audio_path)
        if embedding is None:
            return None

        speaker_id = f"spk_{uuid.uuid4().hex[:12]}"

        # 保存音频文件到声纹目录
        os.makedirs(_VOICE_AUDIO_DIR, exist_ok=True)
        audio_save_path = os.path.join(_VOICE_AUDIO_DIR, f"{speaker_id}.wav")
        try:
            import shutil
            shutil.copy2(audio_path, audio_save_path)
        except Exception as e:
            logger.warning(f"[Voiceprint] 保存声纹音频失败: {e}")
            audio_save_path = ""
        entry = {
            "speaker_id": speaker_id,
            "name": name,
            "remark": remark,
            "audio_path": audio_save_path,
            "embedding": embedding.tolist(),
            "embedding_dim": embedding.shape[0],
            "created_at": datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S"),
        }

        with self._registry_lock:
            self._registry[speaker_id] = entry
            self._save_registry()

        logger.info(f"[Voiceprint] 声纹注册成功: {name} ({speaker_id}) remark={remark}")
        return {
            "speaker_id": speaker_id,
            "name": name,
            "remark": remark,
            "embedding_dim": embedding.shape[0],
            "created_at": entry["created_at"],
        }

    def get_audio_path(self, speaker_id: str) -> Optional[str]:
        """获取注册声纹的音频文件路径。

        Args:
            speaker_id: 声纹ID

        Returns:
            音频文件路径，不存在返回 None
        """
        with self._registry_lock:
            entry = self._registry.get(speaker_id)
            if entry is None:
                return None
            audio_path = entry.get("audio_path", "")
            if audio_path and os.path.exists(audio_path):
                return audio_path
            return None

    # ─── 声纹评分（无阈值，返回所有注册用户的相似度）───

    def score_all(self, audio_data) -> Dict[str, float]:
        """
        对音频段计算与所有注册用户的声纹相似度。
        不设阈值，返回原始分数。

        Args:
            audio_data: 文件路径(str) 或 numpy 数组

        Returns:
            {"name": similarity, ...} 按相似度降序
        """
        if not self._registry:
            return {}
        embedding = self.extract_embedding(audio_data)
        if embedding is None:
            return {}
        scores = {}
        with self._registry_lock:
            for sid, entry in self._registry.items():
                reg_emb = np.array(entry["embedding"])
                sim = self.compute_similarity(embedding, reg_emb)
                name = entry["name"]
                scores.setdefault(name, []).append(sim)
        # 多条目同名的取最大值（max-pooling 消除内容/通道差异）
        max_scores = {name: round(max(v), 4) for name, v in scores.items()}
        return dict(sorted(max_scores.items(), key=lambda x: x[1], reverse=True))

    # ─── 声纹识别 ────────────────────────────────────────

    def identify(self, audio_data, threshold: float = IDENTIFY_THRESHOLD,
                 top_k: int = 3) -> List[Dict[str, Any]]:
        """
        识别音频中的说话人。

        Args:
            audio_data: 文件路径(str) 或 numpy 数组
            threshold: 相似度阈值
            top_k: 返回 top N 匹配结果

        Returns:
            [{"speaker_id": str, "name": str, "similarity": float}, ...]
        """
        if not self._registry:
            return []
        embedding = self.extract_embedding(audio_data)
        if embedding is None:
            return []
        results = []
        with self._registry_lock:
            for sid, entry in self._registry.items():
                reg_emb = np.array(entry["embedding"])
                sim = self.compute_similarity(embedding, reg_emb)
                if sim >= threshold:
                    results.append({
                        "speaker_id": sid,
                        "name": entry["name"],
                        "similarity": round(sim, 4),
                    })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def verify(self, audio_data, speaker_id: str,
               threshold: float = VERIFY_THRESHOLD) -> Dict[str, Any]:
        """
        验证音频是否属于指定说话人。

        Args:
            audio_data: 文件路径(str) 或 numpy 数组
            speaker_id: 说话人 ID
            threshold: 判定为同一人的阈值

        Returns:
            {"is_match": bool, "similarity": float, "name": str}
        """
        with self._registry_lock:
            entry = self._registry.get(speaker_id)
            if entry is None:
                return {"is_match": False, "similarity": 0.0, "name": ""}

        embedding = self.extract_embedding(audio_data)
        if embedding is None:
            return {"is_match": False, "similarity": 0.0, "name": entry["name"]}

        reg_emb = np.array(entry["embedding"])
        sim = self.compute_similarity(embedding, reg_emb)
        return {
            "is_match": sim >= threshold,
            "similarity": round(sim, 4),
            "name": entry["name"],
        }

    def get_speaker_count(self) -> int:
        """获取注册声纹数量。"""
        with self._registry_lock:
            return len(self._registry)

    # ─── 声纹管理 ────────────────────────────────────────

    def list_speakers(self) -> List[Dict[str, Any]]:
        """列出所有注册声纹（不含嵌入向量）。"""
        with self._registry_lock:
            result = []
            for sid, entry in self._registry.items():
                result.append({
                    "speaker_id": sid,
                    "name": entry["name"],
                    "embedding_dim": entry.get("embedding_dim", 0),
                    "created_at": entry.get("created_at", ""),
                })
            return sorted(result, key=lambda x: x["created_at"], reverse=True)

    def get_speaker(self, speaker_id: str) -> Optional[Dict[str, Any]]:
        """获取单个声纹详情。"""
        with self._registry_lock:
            entry = self._registry.get(speaker_id)
            if entry is None:
                return None
            return {
                "speaker_id": speaker_id,
                "name": entry["name"],
                "embedding_dim": entry.get("embedding_dim", 0),
                "created_at": entry.get("created_at", ""),
            }

    def delete_speaker(self, speaker_id: str) -> bool:
        """删除注册声纹。"""
        with self._registry_lock:
            if speaker_id in self._registry:
                del self._registry[speaker_id]
                self._save_registry()
                logger.info(f"[Voiceprint] 已删除声纹: {speaker_id}")
                return True
            return False

    # ─── 持久化 ──────────────────────────────────────────

    def _load_registry(self):
        """从 JSON 加载注册库。"""
        try:
            if os.path.exists(_VOICEPRINTS_PATH):
                with open(_VOICEPRINTS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._registry = data.get("speakers", {})
                logger.info(f"[Voiceprint] 已加载 {len(self._registry)} 条声纹")
            else:
                self._registry = {}
                logger.info("[Voiceprint] 声纹库为空")
        except Exception as e:
            logger.warning(f"[Voiceprint] 加载声纹库失败: {e}")
            self._registry = {}

    def _save_registry(self):
        """持久化注册库到 JSON。"""
        try:
            os.makedirs(_DATA_DIR, exist_ok=True)
            data = {
                "version": 2,
                "updated_at": datetime.now(_CST).strftime("%Y-%m-%d %H:%M:%S"),
                "model": "eres2netv2",
                "speakers": self._registry,
            }
            with open(_VOICEPRINTS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[Voiceprint] 保存声纹库失败: {e}")


# ─── 单例 ────────────────────────────────────────────────

_instance: Optional[VoiceprintService] = None
_instance_lock = threading.Lock()


def get_voiceprint_service() -> VoiceprintService:
    """获取全局 VoiceprintService 单例。"""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = VoiceprintService()
    return _instance


def preload_voiceprint_model():
    """预加载声纹模型（启动时调用）。"""
    svc = get_voiceprint_service()
    svc._load_model()
