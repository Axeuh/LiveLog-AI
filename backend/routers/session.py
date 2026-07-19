"""
Session Router - API endpoints for session management

从 main.py 和 stt.py 提取的所有会话相关端点
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import asyncio
import json
import httpx

from config.config import get_config
from services.opencode_gateway import get_opencode_gateway
from services.stt_session_manager import get_session_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["session"])


# ============ Pydantic Models ============


class SessionSwitchRequest(BaseModel):
    """会话切换请求"""
    session_id: str


class SessionCreateRequest(BaseModel):
    """会话创建请求"""
    title: Optional[str] = None
    directory: Optional[str] = None


class MessageSendRequest(BaseModel):
    """发送消息请求（stt.py 完整版本）"""
    message: str
    prefix_data: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    to_agent: Optional[str] = None


class BindMainTaskRequest(BaseModel):
    """绑定主智能体会话请求"""
    session_id: str


class SessionUpdateTitleRequest(BaseModel):
    """更新会话标题请求"""
    session_id: str
    title: str


class ForAgentRequest(BaseModel):
    """智能体会话请求"""
    agent_type: str
    title: str = ""


# ============ Endpoints from main.py ============


@router.post("/session/for-agent")
async def session_for_agent(request: ForAgentRequest):
    """创建或获取指定智能体的会话（同步到 STTSessionManager）"""
    session_mgr = get_session_manager()
    gw = get_opencode_gateway()

    # 1. 先查本地 STTSessionManager 的 agent 会话绑定
    local_sid = session_mgr.get_agent_session(request.agent_type)
    if local_sid:
        logger.info(f"[ForAgent] 使用本地 agent 会话: {local_sid}")
        return {"success": True, "session_id": local_sid, "source": "local"}

    # 2. 尝试复用 OpenCode agent 的当前会话
    try:
        _cfg = get_config()
        async with httpx.AsyncClient(timeout=10.0) as client:
            status_resp = await client.get(f"{_cfg.OPENCODE_URL}/agent")
            if status_resp.status_code == 200:
                agents = status_resp.json()
                for agent in agents if isinstance(agents, list) else []:
                    if isinstance(agent, dict) and agent.get("id") == request.agent_type:
                        current_sid = agent.get("currentSessionID") or agent.get("sessionID")
                        if current_sid:
                            session_mgr.set_agent_session(request.agent_type, current_sid)
                            session_mgr.set_current_session(current_sid, request.title)
                            logger.info(f"[ForAgent] 复用 OpenCode agent 会话: {current_sid}")
                            return {"success": True, "session_id": current_sid, "source": "existing"}
    except Exception:
        pass

    # 3. 创建新会话并同步到本地
    try:
        _cfg = get_config()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{_cfg.OPENCODE_URL}/session",
                headers={"Content-Type": "application/json"},
                json={"title": request.title or f"{request.agent_type} 会话"}
            )
            if resp.status_code == 200:
                data = resp.json()
                session_id = data.get("id") or data.get("session_id")
                if session_id:
                    session_mgr.set_agent_session(request.agent_type, session_id)
                    session_mgr.set_current_session(session_id, request.title)
                    logger.info(f"[ForAgent] 创建新会话并同步: {session_id}")
                    return {"success": True, "session_id": session_id, "source": "created"}
    except Exception as e:
        logger.error(f"创建智能体会话失败: {e}")

    return {"success": False, "error": "创建会话失败"}


# ============ Endpoints from stt.py ============


@router.get("/session/current")
async def get_current_session():
    """获取当前会话"""
    

    manager = get_session_manager()
    session = manager.get_current_session()

    if session:
        return {
            "session_id": session.session_id,
            "title": session.title,
            "created_at": session.created_at,
            "last_accessed": session.last_accessed,
            "directory": session.directory
        }
    else:
        return {"session_id": None, "message": "无活跃会话"}


@router.post("/session/switch")
async def switch_session(request: SessionSwitchRequest):
    """切换到指定会话（同时切换主智能体和监督智能体）"""
    

    manager = get_session_manager()

    session = manager.switch_session(request.session_id)

    if session:
        # 绑定主智能体到新会话
        manager.set_agent_session("main-task", request.session_id)

        logger.info(f"主智能体会话已切换到: {request.session_id}")

        return {
            "status": "switched",
            "session_id": session.session_id,
            "title": session.title,
            "agent_sessions": {
                "main-task": request.session_id
            }
        }
    else:
        raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/session/update-title")
async def update_session_title(request: SessionUpdateTitleRequest):
    """更新会话标题"""
    

    manager = get_session_manager()
    success = manager.update_session_title(request.session_id, request.title)

    if success:
        return {
            "status": "updated",
            "session_id": request.session_id,
            "title": request.title
        }
    else:
        raise HTTPException(status_code=404, detail="会话不存在")


@router.post("/session/create")
async def create_session(request: SessionCreateRequest):
    """创建新会话"""
    

    manager = get_session_manager()
    gateway = get_opencode_gateway()

    # 创建OpenCode会话
    result = await gateway.create_session(
        title=request.title,
        directory=request.directory
    )

    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"]["detail"])

    session_id = result["data"]["session_id"]

    # 设置为当前会话
    session = manager.set_current_session(
        session_id=session_id,
        title=request.title,
        directory=request.directory
    )

    # 绑定主智能体到新会话
    manager.set_agent_session("main-task", session_id)

    return {
        "status": "created",
        "session_id": session_id,
        "title": session.title,
        "agent_sessions": {
            "main-task": session_id
        }
    }


@router.post("/session/bind-main-task")
async def bind_main_task_session(request: BindMainTaskRequest):
    """
    绑定主智能体会话ID

    用于监督服务启动时设置主智能体的会话ID
    """
    

    manager = get_session_manager()
    manager.set_agent_session("main-task", request.session_id)

    return {
        "status": "bound",
        "agent": "main-task",
        "session_id": request.session_id
    }


@router.post("/session/message")
async def send_session_message(request: MessageSendRequest, raw_request: Request):
    """
    发送消息到OpenCode

    支持指定会话ID或目标智能体
    （合并了 main.py 和 stt.py 的两个版本，使用更完整的 stt.py 实现）
    """
    
    gateway = get_opencode_gateway()
    manager = get_session_manager()

    # 确定目标会话
    session_id = None

    # 优先使用传入的session_id
    if request.session_id:
        session_id = request.session_id
    # 如果指定了目标智能体，获取该智能体的会话
    elif request.to_agent:
        session_id = manager.get_agent_session(request.to_agent)

    # 如果仍然没有会话，使用当前会话或创建新会话
    if not session_id:
        session_id = manager.get_session_id()
        if not session_id:
            # 创建新会话
            result = await gateway.create_session(title="手动消息会话")
            if not result["ok"]:
                raise HTTPException(status_code=500, detail=f"创建会话失败: {result['error']['detail']}")
            session_id = result["data"]["session_id"]
            manager.set_current_session(session_id, "手动消息会话")

    # 设置source名称
    if request.to_agent:
        source_name = request.to_agent
    else:
        source_name = "main-task"

    # 发送消息（传递prefix_data和agent）
    agent_name = request.to_agent if request.to_agent else "main-task"

    # 记录用户消息到感知数据（不含前缀），先于网关调用确保一定写入
    try:
        from services.perception_store import append_perception
        from datetime import datetime, timezone, timedelta
        user_id = getattr(raw_request.state, 'user_id', None)
        entry = {
            "type": "web_message",
            "t": datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S"),
            "content": request.message,
            "source": "web_message",
        }
        if user_id:
            entry["user_qq"] = str(user_id)
        append_perception(entry, auto_type=False)
        logger.debug(f"[Session] 已记录消息到感知数据")
    except Exception as e:
        logger.debug(f"[Session] 记录消息到感知数据异常（不影响消息发送）: {e}")

    send_result = await gateway.send_message(
        session_id=session_id,
        message=request.message,
        prefix_data=request.prefix_data,
        agent=agent_name
    )

    if not send_result["ok"]:
        raise HTTPException(status_code=500, detail=send_result["error"]["detail"])

    # 后台保存会话历史（不阻塞响应）
    try:
        from services.session_history_saver import save_session_history, save_child_sessions
        import asyncio

        async def _save_all(sid, name):
            await save_session_history(sid, header_title=name)
            await save_child_sessions(sid)

        asyncio.create_task(_save_all(session_id, source_name))
    except Exception:
        pass

    return {"status": "sent", "session_id": session_id, "to_agent": request.to_agent, "source": source_name}


@router.post("/session/abort")
async def abort_session():
    """中止当前会话的任务"""
    

    manager = get_session_manager()
    gateway = get_opencode_gateway()

    session = manager.get_current_session()
    if not session:
        return {"status": "no_session", "message": "无活跃会话"}

    result = await gateway.abort_session(session.session_id)

    if not result["ok"]:
        return {"status": "error", "message": result["error"]["detail"]}

    return {"status": "aborted", "session_id": session.session_id}


@router.get("/session/list")
async def list_sessions():
    """列出所有会话"""
    

    manager = get_session_manager()
    gateway = get_opencode_gateway()

    # 获取本地会话历史
    local_sessions = manager.list_sessions()

    # 获取OpenCode会话
    result = await gateway.list_sessions()
    opencode_sessions = result["data"].get("sessions", []) if result["ok"] else []

    # 如果本地会话为空，从 OpenCode 会话中取最近 10 个展示
    display_sessions = local_sessions
    if not display_sessions and opencode_sessions:
        display_sessions = [
            {"session_id": s.get("id"), "title": s.get("slug", "会话"), "created_at": s.get("created_at", "")}
            for s in opencode_sessions[:10]
        ]

    return {
        "local_sessions": display_sessions,
        "opencode_sessions": opencode_sessions,
        "current_session": manager.get_session_id()
    }


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str, limit: int = 100):
    """
    获取指定会话的消息历史

    Args:
        session_id: 会话ID
        limit: 返回消息数量上限（默认100）
    """
    gateway = get_opencode_gateway()
    result = await gateway.get_session_messages(session_id, limit=limit)

    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"]["detail"])

    return {
        "session_id": session_id,
        "messages": result["data"]["messages"],
        "count": len(result["data"]["messages"])
    }


@router.get("/session/stats")
async def session_stats():
    """获取会话统计信息"""
    

    manager = get_session_manager()
    return manager.get_stats()


@router.get("/session/agent/{agent_type}")
async def get_agent_session(agent_type: str):
    """
    获取指定智能体的会话

    Args:
        agent_type: 智能体类型 (voice-interaction, main-task)
    """
    

    manager = get_session_manager()
    session_id = manager.get_agent_session(agent_type)

    return {
        "agent_type": agent_type,
        "session_id": session_id,
        "exists": session_id is not None
    }


@router.post("/session/agent/{agent_type}")
async def create_agent_session(agent_type: str, request: SessionCreateRequest):
    """
    为指定智能体创建会话

    Args:
        agent_type: 智能体类型 (voice-interaction, main-task)
    """
    

    manager = get_session_manager()
    gateway = get_opencode_gateway()

    # 创建OpenCode会话
    result = await gateway.create_session(
        title=request.title or f"{agent_type}智能体会话",
        directory=request.directory
    )

    if not result["ok"]:
        raise HTTPException(status_code=500, detail=result["error"]["detail"])

    session_id = result["data"]["session_id"]

    # 设置为该智能体的会话
    manager.set_agent_session(agent_type, session_id)

    return {
        "status": "created",
        "agent_type": agent_type,
        "session_id": session_id
    }


@router.get("/session/active")
async def get_active_sessions():
    """
    获取正在运行的OpenCode会话列表

    用于前端显示会话泡泡效果
    """
    gateway = get_opencode_gateway()
    result = await gateway.get_active_sessions()

    if not result["ok"]:
        return {"active_sessions": [], "count": 0, "error": result["error"]["detail"]}

    data = result["data"]
    active_sessions = data.get("active_sessions", [])
    return {
        "active_sessions": active_sessions,
        "count": len(active_sessions)
    }


@router.get("/session/{session_id}/children")
async def get_session_children(session_id: str):
    """
    获取会话的子会话/子智能体列表

    调用 OpenCode API /session/{session_id}/children 获取
    子智能体(task工具)创建的子会话信息
    """
    gateway = get_opencode_gateway()
    result = await gateway.get_session_children(session_id)

    if not result["ok"]:
        return {"children": [], "error": result.get("error", {}).get("detail", "未知错误")}

    data = result["data"]
    children = data.get("children", [])
    return {"children": children}
