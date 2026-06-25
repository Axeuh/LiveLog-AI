"""
语音助手 WebSocket 协议数据模型

定义客户端(Android VoiceInteractionSession)与服务器之间的消息格式。
WebSocket 端点: /ws/voice-assistant
"""

from pydantic import BaseModel
from typing import Literal, Any
from enum import Enum
import json


class WSMessageType(str, Enum):
    """WebSocket 消息类型枚举"""
    # 客户端 -> 服务端
    START = "start"
    STOP = "stop"
    AUDIO_START = "audio_start"
    AUDIO_STOP = "audio_stop"
    PING = "ping"
    # 服务端 -> 客户端
    STARTED = "started"
    PARTIAL = "partial"
    STOP_RECORDING = "stop_recording"
    RESULT = "result"
    VOICEPRINT_SCORE = "voiceprint_score"
    VAD_STATE = "vad_state"
    ERROR = "error"
    PONG = "pong"


# ============ 客户端 -> 服务端 消息 ============


class StartCommand(BaseModel):
    """启动语音助手指令"""
    type: Literal["start"] = "start"
    source: str = "android"  # "android" | "web"


class StopCommand(BaseModel):
    """停止语音助手指令"""
    type: Literal["stop"] = "stop"


class AudioStartCommand(BaseModel):
    """开始音频流指令"""
    type: Literal["audio_start"] = "audio_start"
    sample_rate: int = 16000
    channels: int = 1


class AudioStopCommand(BaseModel):
    """停止音频流指令"""
    type: Literal["audio_stop"] = "audio_stop"


class PingCommand(BaseModel):
    """心跳指令"""
    type: Literal["ping"] = "ping"


# ============ 服务端 -> 客户端 消息 ============


class StartedResponse(BaseModel):
    """启动成功响应"""
    type: Literal["started"] = "started"
    source: str
    message: str = "语音助手已启动"


class PartialResult(BaseModel):
    """实时识别中间结果"""
    type: Literal["partial"] = "partial"
    text: str
    segment_id: int
    voiceprint_score: float = 0.0
    is_final: bool = False


class StopRecording(BaseModel):
    """通知客户端停止录音"""
    type: Literal["stop_recording"] = "stop_recording"
    cause: str  # "voiceprint" | "silence" | "manual"


class SegmentInfo(BaseModel):
    """语音段落信息"""
    start_ms: int
    end_ms: int
    speaker: str = "unknown"
    voiceprint_score: float = 0.0
    text: str = ""


class SoundEvent(BaseModel):
    """声音事件"""
    start_ms: int
    end_ms: int
    label: str
    confidence: float = 0.0


class FinalResult(BaseModel):
    """最终识别结果"""
    type: Literal["result"] = "result"
    text: str
    duration_ms: int = 0
    segments: list[SegmentInfo] = []
    voiceprint_log: list[dict[str, Any]] = []
    sound_events: list[SoundEvent] = []


class VoiceprintScore(BaseModel):
    """声纹相似度评分"""
    type: Literal["voiceprint_score"] = "voiceprint_score"
    score: float
    window_ms: int = 500


class VadState(BaseModel):
    """VAD 状态通知"""
    type: Literal["vad_state"] = "vad_state"
    state: str  # "speech" | "silence"


class ErrorResponse(BaseModel):
    """错误响应"""
    type: Literal["error"] = "error"
    message: str


class PongResponse(BaseModel):
    """心跳响应"""
    type: Literal["pong"] = "pong"


# ============ 消息分发 ============

# 客户端消息联合类型
ClientMessage = StartCommand | StopCommand | AudioStartCommand | AudioStopCommand | PingCommand


def parse_client_message(data: str) -> ClientMessage:
    """解析客户端 WebSocket 消息，根据 type 字段自动路由到对应模型

    Args:
        data: JSON 字符串

    Returns:
        对应的消息模型实例

    Raises:
        ValueError: 无法识别的消息类型
        json.JSONDecodeError: JSON 格式错误
    """
    obj = json.loads(data)
    msg_type = obj.get("type", "")

    if msg_type == "start":
        return StartCommand(**obj)
    elif msg_type == "stop":
        return StopCommand(**obj)
    elif msg_type == "audio_start":
        return AudioStartCommand(**obj)
    elif msg_type == "audio_stop":
        return AudioStopCommand(**obj)
    elif msg_type == "ping":
        return PingCommand(**obj)
    else:
        raise ValueError(f"未知消息类型: {msg_type}")
