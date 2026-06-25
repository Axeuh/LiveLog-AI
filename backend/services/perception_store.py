"""
感知数据存储服务

每次 voice-session 完成后存储：
1. 原始音频 WAV → ai/data/{date}/audio/{time}_{user}.wav
2. 感知分析结果 → ai/data/{date}/perception.jsonl（逐行追加，增量）
3. 每日概览 → ai/data/{date}/profile.json（覆盖，每天一条）

数据策略:
  - 覆盖型（profile.json）: 步数、睡眠、App 使用时长 — 每天只保留最新一条
  - 增量型（perception.jsonl）: 心率、GPS、电量、环境声音 — 保持完整时间线

目录结构:
    ai/data/{YYYY-MM-DD}/
    ├── audio/
    │   └── {HH}{MM}{SS}_{user}.wav
    ├── perception.jsonl           # 增量采样
    └── profile.json               # 覆盖概览
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# 东八区
_CST = timezone(timedelta(hours=8))
from config.config import get_config
_cfg_ps = get_config()
_DATA_BASE = _cfg_ps.DATA_DIR


def _today_str() -> str:
    """获取今天的日期字符串（东八区）"""
    return datetime.now(_CST).strftime("%Y-%m-%d")


def _date_dir(date_str: str) -> str:
    """获取某天的数据目录"""
    d = os.path.join(_DATA_BASE, date_str)
    os.makedirs(d, exist_ok=True)
    return d


def _now_time_str() -> str:
    """获取当前时间字符串用于文件名（东八区）"""
    return datetime.now(_CST).strftime("%H%M%S")


def save_profile(profile_data: dict, user_id: str = "default") -> bool:
    """
    保存覆盖型每日概览到 ai/data/{date}/profile.json。
    """
    try:
        date_str = _today_str()
        date_dir = _date_dir(date_str)
        profile_data.setdefault("date", date_str)
        filepath = os.path.join(date_dir, "profile.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)
        logger.info(f"[PerceptionStore] profile 已保存: {filepath}")
        return True
    except Exception as e:
        logger.warning(f"[PerceptionStore] profile 保存失败: {e}")
        return False


def get_today_profile(user_id: str = "default") -> Optional[dict]:
    """
    读取今天的 profile 文件。
    """
    try:
        date_str = _today_str()
        filepath = os.path.join(_date_dir(date_str), "profile.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[PerceptionStore] profile 读取失败: {e}")
        return None


def save_audio(audio_data: bytes, user_id: str = "default") -> Optional[str]:
    """
    保存原始音频到 ai/data/{date}/audio/ 目录。
    """
    try:
        date_str = _today_str()
        time_str = _now_time_str()
        date_dir = _date_dir(date_str)
        audio_dir = os.path.join(date_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        filename = f"{time_str}_{user_id}.wav"
        filepath = os.path.join(audio_dir, filename)
        with open(filepath, "wb") as f:
            f.write(audio_data)

        rel_path = f"{date_str}/audio/{filename}"
        logger.info(f"[PerceptionStore] 音频已保存: {rel_path} ({len(audio_data)}B)")
        return rel_path
    except Exception as e:
        logger.warning(f"[PerceptionStore] 音频保存失败: {e}")
        return None


def append_perception(entry: Dict[str, Any], user_id: str = "default", auto_type: bool = True) -> bool:
    """
    追加一条感知分析结果到 ai/data/{date}/perception.jsonl。
    """
    try:
        date_str = _today_str()
        date_dir = _date_dir(date_str)
        filepath = os.path.join(date_dir, "perception.jsonl")
        if auto_type and "type" not in entry:
            entry["type"] = "sample"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 构建可读摘要（只对重要事件输出 INFO，device_env 等用 DEBUG）
        entry_type = entry.get("type", "?")
        important_types = {"voice", "notify", "app", "media", "sensor", "input", "screen", "web_message"}
        if entry_type in important_types:
            summary_parts = [f"[PerceptionStore] 感知事件已追加 type={entry_type}"]
            if entry_type == "voice":
                asr = entry.get("asr_text", "") or ""
                segs = entry.get("segments", [])
                if asr:
                    summary_parts.append(f"ASR=\"{asr[:100]}{'...' if len(asr) > 100 else ''}\"")
                if segs:
                    summary_parts.append(f"segs={len(segs)}")
                scene = entry.get("scene", "")
                scene_label = ""
                if isinstance(scene, dict):
                    scene_label = scene.get("scene_primary", {}).get("label_cn", "") or scene.get("scene_primary", {}).get("label", "")
                elif isinstance(scene, str):
                    scene_label = scene
                if scene_label:
                    summary_parts.append(f"scene={scene_label}")
                spk = entry.get("speaker", {})
                if spk and isinstance(spk, dict):
                    sn = spk.get("name", "")
                    if sn:
                        summary_parts.append(f"speaker={sn}(sim={spk.get('similarity', 0):.3f})")
                emotion = entry.get("emotion", {})
                if emotion and isinstance(emotion, dict):
                    et = emotion.get("tag") or emotion.get("dominant_emotion", "")
                    if et:
                        summary_parts.append(f"emotion={et}({emotion.get('probability', 0):.2f})")
            elif entry_type in ("notify", "app", "media", "sensor", "input"):
                payload_keys = list(entry.keys() - {"type", "t", "t_iso"})
                summary_parts.append(f"fields={','.join(payload_keys[:6])}")
            logger.info(" | ".join(summary_parts))
        else:
            logger.debug(f"[PerceptionStore] type={entry_type}")
        return True
    except Exception as e:
        logger.warning(f"[PerceptionStore] 感知事件保存失败: {e}")
        return False


def get_today_profile(user_id: str = "default") -> Optional[dict]:
    """
    读取今天的 profile 文件。

    Returns:
        概览字典，文件不存在返回 None
    """
    try:
        date_str = _today_str()
        filepath = os.path.join(_DATA_BASE, date_str, "profile.json")
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[PerceptionStore] 概览读取失败: {e}")
        return None


def save_audio(audio_data: bytes, user_id: str = "default") -> Optional[str]:
    """
    保存原始音频到 ai/data/{date}/audio/。

    Args:
        audio_data: WAV 格式音频字节
        user_id: 用户标识

    Returns:
        相对存储路径（如 audio/120000_user.wav），失败返回 None
    """
    try:
        date_str = _today_str()
        time_str = _now_time_str()
        date_dir = _date_dir(date_str)
        audio_dir = os.path.join(date_dir, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        filename = f"{time_str}_{user_id}.wav"
        filepath = os.path.join(audio_dir, filename)

        with open(filepath, "wb") as f:
            f.write(audio_data)

        rel_path = f"{date_str}/audio/{filename}"
        logger.info(f"[PerceptionStore] 音频已保存: {rel_path} ({len(audio_data)} bytes)")
        return rel_path
    except Exception as e:
        logger.warning(f"[PerceptionStore] 音频保存失败: {e}")
        return None


def append_perception(entry: Dict[str, Any], user_id: str = "default", auto_type: bool = True) -> bool:
    """
    追加一条感知分析结果到当日 jsonl 文件。

    Args:
        entry: 感知事件数据字典
        user_id: 用户标识（预留，目前统一文件）
        auto_type: 是否自动添加 type="sample"

    Returns:
        是否成功
    """
    try:
        date_str = _today_str()
        filepath = os.path.join(_date_dir(date_str), "perception.jsonl")

        if auto_type and "type" not in entry:
            entry["type"] = "sample"

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # 构建可读摘要（只对重要事件输出 INFO，device_env 等用 DEBUG）
        entry_type = entry.get("type", "?")
        important_types = {"voice", "notify", "app", "media", "sensor", "input", "screen", "web_message"}
        if entry_type in important_types:
            summary_parts = [f"[PerceptionStore] {entry_type}"]
            if entry_type == "voice":
                asr = entry.get("asr_text", "") or ""
                segs = entry.get("segments", [])
                if asr:
                    summary_parts.append(f"ASR=\"{asr[:100]}{'...' if len(asr) > 100 else ''}\"")
                if segs:
                    summary_parts.append(f"segs={len(segs)}")
                scene = entry.get("scene", "")
                scene_label = ""
                if isinstance(scene, dict):
                    scene_label = scene.get("scene_primary", {}).get("label_cn", "") or scene.get("scene_primary", {}).get("label", "")
                elif isinstance(scene, str):
                    scene_label = scene
                if scene_label:
                    summary_parts.append(f"scene={scene_label}")
                spk = entry.get("speaker", {})
                if spk and isinstance(spk, dict):
                    sn = spk.get("name", "")
                    if sn:
                        summary_parts.append(f"speaker={sn}(sim={spk.get('similarity', 0):.3f})")
                emotion = entry.get("emotion", {})
                if emotion and isinstance(emotion, dict):
                    et = emotion.get("tag") or emotion.get("dominant_emotion", "")
                    if et:
                        summary_parts.append(f"emotion={et}({emotion.get('probability', 0):.2f})")
            elif entry_type in ("notify", "app", "media", "sensor", "input"):
                payload_keys = list(entry.keys() - {"type", "t", "t_iso"})
                summary_parts.append(f"fields={','.join(payload_keys[:6])}")
            logger.info(" | ".join(summary_parts))
        else:
            logger.debug(f"[PerceptionStore] {entry_type}")
        return True
    except Exception as e:
        logger.warning(f"[PerceptionStore] 感知事件保存失败: {e}")
        return False


def _reset_store():
    """测试用：重置模块状态"""
    pass
