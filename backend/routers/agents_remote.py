# -*- coding: utf-8 -*-
"""
远程 Agent 注册与心跳管理路由
管理远程 Agent 的注册、心跳、列表、详情以及 WebSocket 持活连接
"""
import os
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from starlette.responses import Response
from pydantic import BaseModel

from auth import verify_token

logger = logging.getLogger(__name__)

# 配置文件路径
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_FILE = os.path.join(BACKEND_DIR, "config", "agents.json")

router = APIRouter(tags=["远程Agent管理"])


# ============ Pydantic模型 ============

class RegisterRequest(BaseModel):
    """Agent注册请求"""
    agent_id: str
    agent_name: str
    capabilities: List[str] = []


class HeartbeatRequest(BaseModel):
    """Agent心跳请求"""
    agent_id: str


class AgentInfo(BaseModel):
    """Agent信息"""
    agent_id: str
    agent_name: str
    capabilities: List[str]
    status: str  # online, offline
    connected_at: str
    last_heartbeat: str
    user_id: Optional[str] = None


class SendCommandRequest(BaseModel):
    """向Agent发送命令请求"""
    agent_id: str
    action: str
    params: dict = {}


# ============ JSON文件读写 ============

def load_agents() -> Dict[str, Any]:
    """加载Agent列表"""
    config_dir = os.path.dirname(AGENTS_FILE)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)

    if os.path.exists(AGENTS_FILE):
        with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        save_agents({})
        return {}


def save_agents(agents: Dict[str, Any]):
    """保存Agent列表"""
    config_dir = os.path.dirname(AGENTS_FILE)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir)

    with open(AGENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(agents, f, indent=2, ensure_ascii=False)


# ============ WebSocket 连接管理 ============

# Agent WebSocket 连接映射 {agent_id: WebSocket}
_agent_connections: Dict[str, WebSocket] = {}
# Agent 命令执行结果缓存 {cmd_id: result_data}
_agent_results: Dict[str, Any] = {}
# Agent 待处理命令 Future 映射 {cmd_id: asyncio.Future}
_agent_pending_commands: Dict[str, asyncio.Future] = {}


async def handle_agent_register(websocket: WebSocket, agent_id: str, agent_name: str, capabilities: List[str]) -> None:
    """Agent 注册（WebSocket 版）"""
    now = datetime.now().isoformat()
    agents = load_agents()

    agents[agent_id] = {
        "agent_id": agent_id,
        "agent_name": agent_name,
        "capabilities": capabilities,
        "status": "online",
        "connected_at": now,
        "last_heartbeat": now,
        "user_id": None
    }
    save_agents(agents)

    _agent_connections[agent_id] = websocket
    logger.info(f"[AgentWS] Agent 注册成功: {agent_id} ({agent_name}), capabilities={capabilities}")

    await websocket.send_json({"type": "registered", "agent_id": agent_id})


def mark_agent_offline(agent_id: str) -> None:
    """标记 Agent 离线"""
    agents = load_agents()
    if agent_id in agents:
        agents[agent_id]["status"] = "offline"
        save_agents(agents)
        logger.info(f"[AgentWS] Agent 已标记离线: {agent_id}")


async def send_command_to_agent(agent_id: str, action: str, params: dict = None) -> dict:
    """向 Agent 发送命令，等待结果"""
    if agent_id not in _agent_connections:
        return {"error": "Agent offline"}

    ws = _agent_connections[agent_id]
    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"

    # 创建 Future 等待结果
    future = asyncio.get_event_loop().create_future()
    _agent_pending_commands[cmd_id] = future

    try:
        await ws.send_json({
            "type": "cmd",
            "cmd_id": cmd_id,
            "action": action,
            "params": params or {}
        })

        # 等待结果（默认30秒超时）
        result = await asyncio.wait_for(future, timeout=30)
        return result
    except asyncio.TimeoutError:
        return {"error": "Command timeout"}
    finally:
        if cmd_id in _agent_pending_commands:
            del _agent_pending_commands[cmd_id]


# ============ API端点 ============

@router.post("/register")
async def register_agent(data: RegisterRequest):
    """Agent注册"""
    agents = load_agents()
    now = datetime.now().isoformat()

    agents[data.agent_id] = {
        "agent_id": data.agent_id,
        "agent_name": data.agent_name,
        "capabilities": data.capabilities,
        "status": "online",
        "connected_at": now,
        "last_heartbeat": now,
        "user_id": None
    }
    save_agents(agents)

    return {"success": True, "agent_id": data.agent_id}


@router.post("/heartbeat")
async def agent_heartbeat(data: HeartbeatRequest):
    """Agent心跳"""
    agents = load_agents()
    if data.agent_id not in agents:
        return {"success": False, "error": "Agent not found"}

    now = datetime.now().isoformat()
    agents[data.agent_id]["status"] = "online"
    agents[data.agent_id]["last_heartbeat"] = now
    save_agents(agents)

    return {"success": True, "last_heartbeat": now}


@router.get("/list")
async def list_agents():
    """列出所有Agent"""
    agents = load_agents()
    return list(agents.values())


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """获取Agent详情"""
    agents = load_agents()
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agents[agent_id]


@router.post("/send-command")
async def send_command_to_agent_endpoint(data: SendCommandRequest):
    """向Agent发送命令并等待结果"""
    result = await send_command_to_agent(data.agent_id, data.action, data.params)
    return result


# ============ Agent WebSocket 持活 + 下载路由（精确路径，无前缀）============

ws_dl_router = APIRouter(tags=["Agent持活与下载"])


@ws_dl_router.websocket("/ws/agent")
async def agent_websocket_endpoint(websocket: WebSocket):
    """Agent WebSocket 持活连接"""
    # 验证 Token
    token = websocket.query_params.get("token", "")
    is_valid, user_id = verify_token(token)
    if not is_valid:
        logger.warning(f"[AgentWS] Token验证失败，连接已关闭")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    agent_id = None

    try:
        logger.info("[AgentWS] 新的 Agent WebSocket 连接")
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "register":
                agent_id = data.get("agent_id")
                agent_name = data.get("agent_name", agent_id)
                capabilities = data.get("capabilities", [])
                if agent_id:
                    await handle_agent_register(websocket, agent_id, agent_name, capabilities)
                    _agent_connections[agent_id] = websocket

            elif msg_type == "heartbeat":
                if agent_id:
                    agents = load_agents()
                    if agent_id in agents:
                        agents[agent_id]["status"] = "online"
                        agents[agent_id]["last_heartbeat"] = datetime.now().isoformat()
                        save_agents(agents)
                await websocket.send_json({"type": "heartbeat_ack"})

            elif msg_type == "result":
                cmd_id = data.get("cmd_id")
                result_data = data.get("data", {})
                if cmd_id:
                    _agent_results[cmd_id] = result_data
                    if cmd_id in _agent_pending_commands:
                        _agent_pending_commands[cmd_id].set_result(result_data)

    except WebSocketDisconnect:
        if agent_id:
            logger.info(f"[AgentWS] Agent 断开连接: {agent_id}")
            mark_agent_offline(agent_id)
            if agent_id in _agent_connections:
                del _agent_connections[agent_id]
    except Exception as e:
        logger.error(f"[AgentWS] WebSocket 错误: {e}")
        if agent_id:
            mark_agent_offline(agent_id)
            if agent_id in _agent_connections:
                del _agent_connections[agent_id]


@ws_dl_router.get("/api/agent/download")
async def download_agent_client():
    """下载 axeuh-agent 客户端 ZIP 包"""
    import zipfile
    import io

    AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agent")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in ["agent_server.py", "config.json", "requirements.txt", "build.bat", "README.md"]:
            filepath = os.path.join(AGENT_DIR, filename)
            if os.path.exists(filepath):
                zf.write(filepath, f"axeuh-agent/{filename}")

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=axeuh-agent.zip"
        }
    )
