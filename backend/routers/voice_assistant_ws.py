"""
语音助手 WebSocket 路由 - /ws/voice-assistant

接收 Android VoiceInteractionSession (及后续 Web 客户端) 的 PCM 音频流，
路由到 VoiceAssistantService，通过事件回调转发识别结果到 WebSocket 客户端。

依赖:
- services.voice_assistant_service.get_voice_assistant_service()
- (延迟导入) services.voice_assistant_models.parse_client_message
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Any
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice-assistant-websocket"])


async def _map_event_to_message(event_type: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """将 VoiceAssistantService 事件映射为 WebSocket JSON 消息

    Args:
        event_type: 服务事件类型 (started, vad_state, voiceprint_score, partial, ...)
        data: 事件数据字典

    Returns:
        WebSocket JSON 消息字典，None 表示无需发送
    """
    if event_type == "started":
        return {
            "type": "started",
            "source": data.get("source", ""),
            "message": "语音助手已启动",
        }
    elif event_type == "vad_state":
        return {
            "type": "vad_state",
            "state": data.get("state", ""),
        }
    elif event_type == "voiceprint_score":
        return {
            "type": "voiceprint_score",
            "score": data.get("score", 0.0),
            "window_ms": data.get("window_ms", 500),
        }
    elif event_type == "partial":
        return {
            "type": "partial",
            "text": data.get("text", ""),
            "segment_id": data.get("segment_id", 0),
            "voiceprint_score": data.get("avg_voiceprint", 0.0),
        }
    elif event_type == "stop_recording":
        return {
            "type": "stop_recording",
            "cause": data.get("cause", "manual"),
        }
    elif event_type == "result":
        return {
            "type": "result",
            "text": data.get("text", ""),
            "duration_ms": data.get("duration_ms", 0),
            "segments": data.get("segments", []),
            "sound_events": data.get("sound_events", []),
        }
    elif event_type == "error":
        return {
            "type": "error",
            "message": data.get("message", "未知错误"),
        }
    return None


@router.websocket("/ws/voice-assistant")
async def voice_assistant_ws(websocket: WebSocket):
    """
    WebSocket 端点 - 语音助手实时音频流

    消息类型 (Client -> Server):
        - {"type": "start", "source": "android"} - 启动语音助手
        - {"type": "stop"} - 停止语音助手
        - {"type": "audio_start", "sampleRate": 16000, "channels": 1} - 开始音频流
        - {"type": "audio_stop"} - 停止音频流
        - {"type": "ping"} - 心跳
        - {"type": "status"} - 获取状态
        - Binary data - PCM 16bit/16kHz/mono 音频数据

    消息类型 (Server -> Client):
        - {"type": "connected", "message": "...", "status": {...}}
        - {"type": "started", "source": "...", "message": "语音助手已启动"}
        - {"type": "vad_state", "state": "speech|silence"}
        - {"type": "voiceprint_score", "score": 0.72, "window_ms": 500}
        - {"type": "partial", "text": "...", "segment_id": 1, "voiceprint_score": 0.72}
        - {"type": "stop_recording", "cause": "voiceprint|silence|manual"}
        - {"type": "result", "text": "...", "duration_ms": 4120, "segments": [...]}
        - {"type": "error", "message": "..."}
        - {"type": "pong"}
        - {"type": "audio_started"}
        - {"type": "audio_stopped"}
        - {"type": "status", ...}
    """
    # 延迟导入，避免启动时加载服务依赖
    from services.voice_assistant_service import get_voice_assistant_service

    await websocket.accept()
    logger.info("[VAWS] 新的语音助手 WebSocket 连接")

    service = get_voice_assistant_service()
    audio_stream_active = False

    # ========== 服务事件 -> WS 消息桥接 ==========

    async def _send_event(event_type: str, data: dict[str, Any]) -> None:
        """异步发送服务事件到 WebSocket 客户端"""
        try:
            msg = await _map_event_to_message(event_type, data)
            if msg is not None:
                await websocket.send_json(msg)
        except Exception as e:
            # 连接可能已关闭，仅记录调试日志
            logger.debug(f"[VAWS] 事件发送失败 {event_type}: {e}")

    def on_service_event(event_type: str, data: dict[str, Any]) -> None:
        """服务事件回调 - 同步桥接到异步发送"""
        try:
            # 直接用 loop.create_task 调度（代替 run_coroutine_threadsafe，更可靠）
            loop = asyncio.get_running_loop()
            loop.create_task(_send_event(event_type, data))
        except Exception as e:
            logger.error(f"[VAWS] 事件调度失败 {event_type}: {e}")

    # 注册服务回调
    service.on_event(on_service_event)

    # 发送初始连接状态
    await websocket.send_json({
        "type": "connected",
        "message": "语音助手已连接",
        "status": service.get_status(),
    })

    try:
        while True:
            message = await websocket.receive()
            logger.info(f"[VAWS] 收到消息 type={message.get('type')}")

            if message.get("text") is not None:
                # 文本消息：JSON 命令
                try:
                    msg_data = json.loads(message["text"])
                    msg_type = msg_data.get("type", "")

                    if msg_type == "start":
                        source = msg_data.get("source", "android")
                        # 确保服务状态干净
                        if service.get_status().get("running", False):
                            service.stop()
                        service.start(source=source)
                        logger.info(f"[VAWS] 语音助手已启动, source={source}")
                        await websocket.send_json({
                            "type": "started",
                            "source": source,
                            "message": "语音助手已启动",
                        })

                    elif msg_type == "stop":
                        service.stop()
                        # 服务通过回调发送 "result" 等事件

                    elif msg_type == "audio_start":
                        audio_stream_active = True
                        await websocket.send_json({
                            "type": "audio_started",
                            "sampleRate": msg_data.get("sampleRate", 16000),
                            "channels": msg_data.get("channels", 1),
                        })
                        logger.info("[VAWS] 音频流已激活")

                    elif msg_type == "audio_stop":
                        audio_stream_active = False
                        await websocket.send_json({"type": "audio_stopped"})
                        logger.info("[VAWS] 音频流已停止")

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif msg_type == "status":
                        await websocket.send_json({
                            "type": "status",
                            **service.get_status(),
                        })

                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"未知消息类型: {msg_type}",
                        })

                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "无效的 JSON 格式",
                    })

            elif message.get("bytes") is not None:
                # 二进制消息：PCM 音频数据
                if audio_stream_active:
                    try:
                        service.feed_audio(message["bytes"])
                    except Exception as e:
                        logger.error(f"[VAWS] 处理音频数据错误: {e}")
                else:
                    logger.warning("[VAWS] 收到音频数据但音频流未激活")

    except WebSocketDisconnect:
        logger.info("[VAWS] WebSocket 客户端断开连接")
    except Exception as e:
        logger.error(f"[VAWS] WebSocket 连接异常: {e}")
    finally:
        # 连接关闭时确保服务停止
        try:
            if service.get_status().get("running", False):
                service.stop()
                logger.info("[VAWS] 服务已随连接关闭而停止")
        except Exception:
            pass
        logger.info("[VAWS] 语音助手 WebSocket 连接已清理")
