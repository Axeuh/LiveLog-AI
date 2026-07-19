"""
WebSocket 主路由 - /ws 端点
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
from typing import Optional

from auth import verify_token
from services.component_manager import component_manager
from services.event_loop_manager import get_main_loop

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """Main WebSocket endpoint - 支持文本和二进制消息"""
    client_host = websocket.client.host if websocket.client else "external"

    ws_user_id = None  # WebSocket 关联的 user_id

    # 先 accept 再验证 token（ASGI 规范要求 send 前必须先 accept）
    await websocket.accept()

    is_valid, ws_user_id = verify_token(token)
    if not is_valid:
        await websocket.send_json({
            "type": "error",
            "message": "未授权访问，请提供有效 token"
        })
        await websocket.close()
        return
    component_manager.add_ws_client(websocket, user_id=ws_user_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket connected"
        })

        await websocket.send_json({
            "type": "initial_state",
            "components": component_manager.get_all(user_id=ws_user_id)
        })

        while True:
            # 接收消息（支持文本和二进制）
            message = await websocket.receive()

            # 忽略内部断开事件（Starlette 有时会下发 websocket.disconnect）
            if isinstance(message, dict) and message.get("type") == "websocket.disconnect":
                break

            # 调试：记录首次收到的消息类型
            if not hasattr(websocket_endpoint, '_first_msg_logged'):
                websocket_endpoint._first_msg_logged = True
                logger.info(f"[WS] 首次收到消息，类型: {message.get('type', 'unknown')}, keys: {list(message.keys())}")

            if "text" in message:
                # 文本消息（JSON控制消息）
                try:
                    data = json.loads(message["text"])
                    await handle_ws_message(websocket, data, ws_user_id)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })

            elif "bytes" in message:
                # 二进制消息（音频数据）
                logger.debug(f"[WS] 收到二进制消息，大小: {len(message['bytes'])} bytes")
                await handle_audio_message(websocket, message["bytes"])
            else:
                logger.warning(f"[WS] 收到未知类型消息: {message}")

        # 连接结束，清理
        component_manager.remove_ws_client(websocket)

    except WebSocketDisconnect:
        component_manager.remove_ws_client(websocket)
        logger.info("[WS] WebSocket disconnected")
    except Exception as e:
        logger.error(f"[WS] WebSocket error: {e}")
        component_manager.remove_ws_client(websocket)


async def _audio_send_to_opencode(text: str, agent: str = "main-task"):
    """发送ASR识别结果到OpenCode（通过统一网关）"""
    if not text:
        logger.warning("[ASR] _audio_send_to_opencode 收到空文本")
        return
    logger.info(f"[ASR] _audio_send_to_opencode: text={text[:60]}..., agent={agent}")
    try:
        from services.opencode_gateway import get_opencode_gateway
        gateway = get_opencode_gateway()
        result = await gateway.send_voice_to_opencode(text, agent=agent)
        if result:
            logger.info(f"[ASR] send_voice_to_opencode 成功")
        else:
            logger.warning(f"[ASR] send_voice_to_opencode 返回 False")
    except Exception as e:
        logger.error(f"[ASR] 发送到OpenCode失败: {e}")


async def handle_audio_message(websocket: WebSocket, audio_data: bytes):
    """
    处理音频数据消息

    接收前端发送的PCM音频数据，转发给VAD/ASR服务处理
    """
    from services.vad_asr_service import get_vad_service

    # 调试：记录首次接收音频数据
    if not hasattr(handle_audio_message, '_first_received'):
        handle_audio_message._first_received = True
        handle_audio_message._audio_buffer = b''
        handle_audio_message._recording = False
        logger.info(f"[WS] 首次接收到音频数据, 大小: {len(audio_data)} bytes")

    # 可选：调试模式下的音频分析（仅在需要时启用）
    debug_audio = False
    if debug_audio and len(audio_data) >= 2:
        import numpy as np
        audio_array = np.frombuffer(audio_data, dtype=np.int16)
        if len(audio_array) > 0:
            logger.info(f"[WS-AUDIO] 大小:{len(audio_data)}B 样本:{len(audio_array)} 范围:[{audio_array.min()},{audio_array.max()}] 均值:{audio_array.mean():.1f} 标准差:{audio_array.std():.1f}")

    vad_service = get_vad_service()
    if vad_service:
        if vad_service._use_external_audio:
            # 将音频数据喂给VAD服务
            vad_service.feed_audio(audio_data)
            # 每秒打印一次日志（避免刷屏）
            if not hasattr(handle_audio_message, '_counter'):
                handle_audio_message._counter = 0
                handle_audio_message._last_log = 0
            handle_audio_message._counter += 1
            if handle_audio_message._counter - handle_audio_message._last_log >= 200:
                logger.info(f"[WS] 已接收 {handle_audio_message._counter} 个音频块, 大小: {len(audio_data)} bytes")
                handle_audio_message._last_log = handle_audio_message._counter
        else:
            logger.warning("[WS] 收到音频数据，但VAD服务未启用外部音频模式")
    else:
        logger.warning("[WS] 收到音频数据，但VAD服务未初始化")


async def handle_ws_message(websocket: WebSocket, message: dict, user_id: Optional[str] = None):
    """Handle WebSocket message"""
    msg_type = message.get("type")

    if msg_type == "ping":
        await websocket.send_json({"type": "pong"})

    elif msg_type == "get_components":
        await websocket.send_json({
            "type": "components_list",
            "components": component_manager.get_all(user_id=user_id)
        })

    elif msg_type == "terminal_input":
        # Send input to terminal
        from services.terminal_service import terminal_manager
        terminal_id = message.get("terminal_id")
        data = message.get("data", "")
        session = terminal_manager.get_session(terminal_id)
        if session and session.terminal:
            session.terminal.write(data)

    elif msg_type == "audio_start":
        # 前端开始发送音频流
        from services.vad_asr_service import get_vad_service, set_external_audio_mode

        sample_rate = message.get("sampleRate", 16000)
        channels = message.get("channels", 1)

        vad_service = get_vad_service()

        if vad_service:
            # 如果VAD服务正在运行，需要先停止再以外部音频模式重启
            if vad_service._is_running:
                logger.info("[WS] VAD服务正在运行，切换到外部音频模式...")
                # 设置外部音频模式标志
                vad_service._use_external_audio = True
            else:
                # VAD服务未运行，启动并设置外部音频模式
                logger.info("[WS] VAD服务未运行，启动外部音频模式...")
                vad_service.start(use_external_audio=True)

            # 获取用户设置的agent偏好
            target_agent = message.get("targetAgent", "main-task")
            logger.info(f"[WS] 音频流开始，agent目标: {target_agent}")

            # 设置结果发送到OpenCode的回调
            def on_result_send(text):
                """发送识别结果到OpenCode"""
                loop = get_main_loop()
                if loop and loop.is_running():
                    future = asyncio.run_coroutine_threadsafe(
                        _audio_send_to_opencode(text, agent=target_agent),
                        loop
                    )
                    try:
                        future.result(timeout=30)
                    except Exception as e:
                        logger.error(f"[WS] on_result_send 发送到OpenCode失败: {e}")
            vad_service.on_result_send(on_result_send)

            logger.info(f"[WS] 音频流开始，采样率: {sample_rate}, 声道: {channels}")
            await websocket.send_json({
                "type": "audio_started",
                "message": "音频流已启动",
                "sampleRate": sample_rate,
                "channels": channels
            })
        else:
            logger.warning("[WS] VAD服务未初始化，尝试启动...")
            # 尝试启动VAD服务（外部音频模式）
            from services.vad_asr_service import VADASRService, WakeWordConfig, set_vad_service
            try:
                wake_config = WakeWordConfig()
                wake_config.WAKE_WORDS = ['小贺同学']
                new_service = VADASRService(wake_word_config=wake_config)
                set_vad_service(new_service)
                new_service.start(use_external_audio=True)
                logger.info("[WS] VAD服务已启动（外部音频模式）")
                await websocket.send_json({
                    "type": "audio_started",
                    "message": "VAD服务已启动"
                })
            except Exception as e:
                logger.error(f"[WS] 启动VAD服务失败: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"VAD服务启动失败: {str(e)}"
                })

    elif msg_type == "tts_playback_complete":
        # 前端通知TTS音频已播放完毕（用于continue_chat流程）
        from routers.stt import notify_tts_playback_complete
        notify_tts_playback_complete()

    elif msg_type == "audio_stop":
        # 前端停止发送音频流
        from services.vad_asr_service import set_external_audio_mode, get_vad_service

        # 如果 VAD 正在录音，立即触发识别
        vad_service = get_vad_service()
        if vad_service and vad_service._is_awake and vad_service._recording:
            logger.info("[WS] 音频流停止，触发ASR识别...")
            # 在新线程中执行 ASR，避免阻塞 WebSocket
            import threading

            def trigger_asr():
                try:
                    # 合并录音
                    audio_data = b''.join(vad_service._recording)
                    vad_service._recording = []

                    logger.info(f"[ASR] 强制识别... (时长: {len(audio_data)/32000:.1f}s)")
                    result = vad_service._recognize_audio(audio_data)
                    result = vad_service._to_simplified(result)

                    if result:
                        logger.info(f"[ASR] 结果: {result}")
                        # 广播结果到前端
                        try:
                            from services.component_manager import component_manager
                            from services.event_loop_manager import get_main_loop
                            import asyncio

                            loop = get_main_loop()
                            if loop:
                                future = asyncio.run_coroutine_threadsafe(
                                    component_manager.broadcast({
                                        "type": "transcription",
                                        "text": result,
                                        "is_final": True
                                    }),
                                    loop
                                )
                                future.result(timeout=5)
                        except Exception as e:
                            logger.error(f"[ASR] 广播错误: {e}")

                        # 也发送到OpenCode（与 _audio_loop 的行为一致）
                        try:
                            if vad_service._on_result_send:
                                logger.info(f"[ASR] trigger_asr调用 _on_result_send: {result[:50]}...")
                                vad_service._on_result_send(result)
                            else:
                                logger.warning(f"[ASR] trigger_asr: _on_result_send 为 None，消息未发送到 OpenCode: {result[:50]}...")
                        except Exception as e:
                            logger.error(f"[ASR] audio_stop触发发送到OpenCode失败: {e}")
                    else:
                        logger.warning("[ASR] 识别结果为空")
                except Exception as e:
                    logger.error(f"[ASR] 强制识别错误: {e}")

            threading.Thread(target=trigger_asr, daemon=True).start()

        set_external_audio_mode(False)
        logger.info("[WS] 音频流已停止")
        await websocket.send_json({
            "type": "audio_stopped",
            "message": "音频流已停止"
        })

    elif msg_type == "force_wake":
        # 手动唤醒
        from services.vad_asr_service import get_vad_service

        vad_service = get_vad_service()
        if vad_service:
            vad_service.force_wake()
            logger.info("[WS] 手动唤醒")
            await websocket.send_json({
                "type": "status",
                "is_awake": True,
                "message": "已手动唤醒"
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "VAD服务未初始化"
            })

    elif msg_type == "force_sleep":
        # 手动休眠
        from services.vad_asr_service import get_vad_service

        vad_service = get_vad_service()
        if vad_service:
            vad_service.force_sleep()
            logger.info("[WS] 手动休眠")
            await websocket.send_json({
                "type": "status",
                "is_awake": False,
                "message": "已手动休眠"
            })
        else:
            await websocket.send_json({
                "type": "error",
                "message": "VAD服务未初始化"
            })

    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })
