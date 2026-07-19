"""
OpenCode Event Proxy - SSE事件代理
将OpenCode的事件流转发给前端
"""
import asyncio
import aiohttp
import json
import logging
from typing import Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

# OpenCode事件流地址 — 从统一配置读取
from config.config import get_config
_cfg_ev = get_config()
OPENCODE_EVENT_URL = f"{_cfg_ev.OPENCODE_URL}/global/event"


def get_session_source_map():
    """
    获取session_id到source的映射
    SSEForwarder 已移除（监督智能体清理），返回空映射
    """
    return {}


async def event_generator():
    """生成SSE事件流"""
    logger.info("[EventProxy] Connecting to OpenCode event stream...")
    
    try:
        # 创建自定义connector
        connector = aiohttp.TCPConnector()
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=None, connect=30)
        ) as session:
            async with session.get(OPENCODE_EVENT_URL) as response:
                if response.status != 200:
                    logger.error(f"[EventProxy] Failed to connect: {response.status}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Connection failed: {response.status}'})}\n\n"
                    return
                
                logger.info("[EventProxy] Connected to OpenCode event stream")
                yield f"data: {json.dumps({'type': 'proxy.connected'})}\n\n"
                
                # 手动读取流，跳过过大的行
                buffer = b""
                
                async for chunk in response.content.iter_any():
                    if chunk:
                        buffer += chunk
                        
                        # 处理缓冲区中的完整行
                        while b'\n' in buffer:
                            line_bytes, buffer = buffer.split(b'\n', 1)
                            line = line_bytes.decode('utf-8', errors='replace').strip()
                            
                            if not line:
                                continue
                            
                            # 跳过过大的行（超过1MB）
                            if len(line) > 1024 * 1024:
                                logger.warning(f"[EventProxy] Skipping large line: {len(line)} bytes")
                                continue
                            
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                try:
                                    data = json.loads(data_str)
                                    
                                    # 解析payload获取session_id
                                    payload = data.get('payload', {})
                                    properties = payload.get('properties', {})
                                    session_id = properties.get('sessionID', '')
                                    
                                    # 添加source字段
                                    source_map = get_session_source_map()
                                    if session_id in source_map:
                                        data['source'] = source_map[session_id]
                                    else:
                                        data['source'] = 'main'
                                    
                                    yield f"data: {json.dumps(data)}\n\n"
                                except json.JSONDecodeError:
                                    # 无法解析，直接转发
                                    yield f"data: {data_str}\n\n"
                            elif line:
                                # 其他内容
                                yield f"data: {line}\n\n"
                
                # 处理缓冲区中剩余的内容
                if buffer:
                    line = buffer.decode('utf-8', errors='replace').strip()
                    if line and len(line) <= 1024 * 1024:
                        if line.startswith("data:"):
                            yield f"data: {line[5:].strip()}\n\n"
                        elif line:
                            yield f"data: {line}\n\n"
                            
    except aiohttp.ClientError as e:
        logger.error(f"[EventProxy] Connection error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    except Exception as e:
        logger.error(f"[EventProxy] Unexpected error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    finally:
        logger.info("[EventProxy] Disconnected from OpenCode event stream")
        yield f"data: {json.dumps({'type': 'proxy.disconnected'})}\n\n"


@router.get("/events/stream")
async def event_stream():
    """
    SSE事件流端点 - 代理OpenCode事件
    
    前端通过此端点接收OpenCode的实时事件
    """
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )