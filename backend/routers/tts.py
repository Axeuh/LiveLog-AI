"""
TTS Router - TTS语音合成路由
"""
import asyncio
import base64
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from services.tts_player import get_tts_player, stop_tts
from services.component_manager import component_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tts"])


class TTSSpeakRequest(BaseModel):
    """TTS请求"""
    text: str
    voice: Optional[str] = None
    style: Optional[str] = None
    user_id: Optional[str] = None  # 目标用户ID，不传则广播
    send_audio: Optional[bool] = False  # 是否发送音频数据到前端


class TTSSynthesizeRequest(BaseModel):
    """TTS合成请求（仅合成，不播放）"""
    text: str
    voice: Optional[str] = None
    style: Optional[str] = None


class TTSSynthesizeResponse(BaseModel):
    """TTS合成响应"""
    status: str
    audio: Optional[str] = None  # Base64编码的音频数据
    error: Optional[str] = None


@router.post("/tts/speak")
async def tts_speak(tts_request: TTSSpeakRequest, fastapi_request: Request):
    """
    TTS语音合成并播放
    
    异步播放，立即返回，不等待播放完成
    如果send_audio=True，则广播音频数据到前端
    """
    # 优先取请求体中传入的user_id（AI工具可携带），否则从请求状态获取（AuthMiddleware注入）
    target_user_id = tts_request.user_id or (
        getattr(fastapi_request.state, 'user_id', None) if hasattr(fastapi_request, 'state') else None
    )
    
    player = get_tts_player()
    
    # 调试日志：打印收到的参数
    logger.info(f"[TTS] 收到TTS请求: text={tts_request.text[:50] if tts_request.text else ''}..., send_audio={tts_request.send_audio}")
    
    if tts_request.send_audio:
        # 新模式：合成音频并发送到前端播放
        asyncio.create_task(synthesize_and_broadcast(
            player,
            tts_request.text,
            tts_request.voice,
            tts_request.style,
            target_user_id=target_user_id
        ))
    else:
        # 原有模式：本地播放
        # 通知前端TTS开始
        await component_manager.broadcast({
            "type": "tts_start",
            "text": tts_request.text if tts_request.text else ""
        }, target_user_id=target_user_id)
        
        # 启动后台播放任务
        asyncio.create_task(play_tts_async(
            player, 
            tts_request.text, 
            tts_request.voice, 
            tts_request.style,
            target_user_id=target_user_id
        ))
    
    return {"status": "sent", "message": "TTS请求已发送"}


@router.post("/tts/synthesize", response_model=TTSSynthesizeResponse)
async def tts_synthesize(request: TTSSynthesizeRequest):
    """
    TTS合成（仅合成音频数据，不播放）
    
    返回Base64编码的WAV音频数据，供前端Web Audio API播放
    """
    player = get_tts_player()
    
    try:
        audio_bytes, error = await player.synthesize_to_bytes(
            text=request.text,
            voice=request.voice,
            style=request.style
        )
        
        if error:
            return TTSSynthesizeResponse(
                status="error",
                error=error
            )
        
        if audio_bytes:
            # 转换为Base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            return TTSSynthesizeResponse(
                status="success",
                audio=audio_base64
            )
        else:
            return TTSSynthesizeResponse(
                status="error",
                error="音频合成失败"
            )
            
    except Exception as e:
        logger.error(f"TTS合成失败: {e}")
        return TTSSynthesizeResponse(
            status="error",
            error=str(e)
        )


async def synthesize_and_broadcast(player, text: str, voice: str = None, style: str = None, target_user_id: str = None):
    """合成完整文本为一段音频并广播到前端（不再拆分句子，避免手机端音频叠加）"""
    try:
        logger.info(f"[TTS] 完整合成: 文本长度={len(text)}字")
        
        # 通知前端TTS开始
        await component_manager.broadcast({
            "type": "tts_start",
            "text": text if text else "",
            "chunk_total": 1,
            "stream": False
        }, target_user_id=target_user_id)
        
        # 完整文本合成一次
        audio_bytes, error = await player.synthesize_to_bytes(
            text=text,
            voice=voice,
            style=style
        )
        
        if error:
            logger.error(f"[TTS] 合成失败: {error}")
            await component_manager.broadcast({
                "type": "tts_error",
                "error": error
            }, target_user_id=target_user_id)
            return
        
        if audio_bytes:
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            await component_manager.broadcast({
                "type": "tts_audio",
                "text": text,
                "audio": audio_base64,
                "format": "wav"
            }, target_user_id=target_user_id)
            logger.info(f"[TTS] 完整合成已广播: {len(audio_bytes)}字节")
        
        # 通知前端TTS结束
        await component_manager.broadcast({
            "type": "tts_end"
        }, target_user_id=target_user_id)
        logger.info("[TTS] 完整合成完成")
        
    except Exception as e:
        logger.error(f"[TTS] 完整合成失败: {e}")
        await component_manager.broadcast({
            "type": "tts_error",
            "error": str(e)
        }, target_user_id=target_user_id)


async def play_tts_async(player, text: str, voice: str = None, style: str = None, target_user_id: str = None):
    """后台播放TTS（原有本地播放模式）"""
    try:
        success = await player.speak_async(
            text=text,
            voice=voice,
            style=style
        )
        
        # 通知前端TTS结束
        await component_manager.broadcast({
            "type": "tts_end"
        }, target_user_id=target_user_id)
        
    except Exception as e:
        logger.error(f"TTS播放失败: {e}")
        await component_manager.broadcast({
            "type": "tts_error",
            "error": str(e)
        }, target_user_id=target_user_id)


@router.post("/tts/stop")
async def tts_stop():
    """停止TTS播放"""
    stop_tts()
    return {"status": "stopped", "message": "TTS已停止"}


@router.get("/tts/status")
async def tts_status():
    """获取TTS状态"""
    player = get_tts_player()
    return {
        "is_playing": player.is_playing
    }