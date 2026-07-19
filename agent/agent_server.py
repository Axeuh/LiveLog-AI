# -*- coding: utf-8 -*-
"""
Windows 智能体 HTTP API 服务

提供截图、文件浏览、文件读写、命令执行、系统信息等端点。
所有端点需 Bearer token 认证。

启动方式:
    python agent_server.py
"""

import io
import json
import os
import platform
import socket
import subprocess
import logging
from datetime import datetime
from typing import Any, Optional

import asyncio
import websockets
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, HTMLResponse
from pydantic import BaseModel

# PC 感知采集器
from pc_sensor import SensorManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("agent_server")

# ============================================================
# 配置
# ============================================================

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        logger.warning("配置文件不存在，使用默认配置: %s", CONFIG_PATH)
        return {
            "agent_id": "default-agent",
            "agent_name": "我的电脑",
            "server_host": "0.0.0.0",
            "server_port": 18888,
            "agent_token": "change-me-to-a-secure-token",
        }
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


config = load_config()

# PC 感知采集管理器（全局单例）
PC_SENSOR_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pc_sensor_config.json"
)
pc_sensor_manager = SensorManager(config_path=PC_SENSOR_CONFIG_PATH)

# ============================================================
# 路径安全 - 黑名单目录
# ============================================================

BLOCKED_PATHS = [
    "C:\\Windows\\System32",
    "C:\\Windows\\",
    "C:\\Windows",
    "\\Windows\\System32",
    "\\Windows",
]

# 规范化黑名单路径（统一小写 + 标准化分隔符）
_BLOCKED_PATHS_NORMALIZED = []
for p in BLOCKED_PATHS:
    normalized = os.path.normpath(p).lower()
    if normalized not in _BLOCKED_PATHS_NORMALIZED:
        _BLOCKED_PATHS_NORMALIZED.append(normalized)


def is_path_blocked(requested_path: str) -> bool:
    """
    检查请求的路径是否在黑名单中。
    如果请求路径是黑名单路径或其子路径，则返回 True。
    """
    try:
        normalized = os.path.normpath(requested_path).lower()
        for blocked in _BLOCKED_PATHS_NORMALIZED:
            if normalized == blocked or normalized.startswith(blocked + os.sep):
                return True
            # 处理无盘符的情况（如 \\Windows\\System32）
            if blocked.startswith("c:"):
                blocked_no_drive = blocked[2:]
                if normalized.endswith(blocked_no_drive) or normalized.startswith(
                    blocked_no_drive.lstrip("\\")
                ):
                    return True
    except Exception:
        pass
    return False


# ============================================================
# 命令安全 - 黑名单命令
# ============================================================

ALLOWED_COMMAND_PATTERNS = [
    "dir", "ls", "cd", "pwd", "echo", "type", "cat", "find", "findstr",
    "ping", "ipconfig", "netstat", "tasklist", "systeminfo", "ver",
    "whoami", "hostname", "date", "time", "chcp", "set", "path",
    "copy", "xcopy", "robocopy", "move", "rename", "ren", "mkdir", "md",
    "rmdir", "del", "erase", "attrib", "cacls", "icacls",
    "more", "sort", "fc", "comp", "tree",
]


def is_command_blocked(command: str) -> bool:
    """检查命令是否允许执行（白名单模式）"""
    cmd_lower = command.lower().strip()
    # 提取命令的第一个词（命令名）
    cmd_name = cmd_lower.split()[0] if cmd_lower.split() else ""
    if not cmd_name:
        return True
    # 检查是否在白名单中
    for pattern in ALLOWED_COMMAND_PATTERNS:
        if cmd_name == pattern or cmd_name.startswith(pattern):
            return False
    # 不在白名单中的命令视为不安全
    return True


# ============================================================
# FastAPI 应用
# ============================================================

app = FastAPI(
    title="Axeuh Windows Agent",
    description="Windows 智能体 HTTP API 服务 - 提供远程桌面管理能力",
    version="1.0.0",
)

# CORS 配置（允许所有来源，因为 agent 是独立服务）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Token 认证
# ============================================================

AGENT_TOKEN = config.get("agent_token", "")


async def verify_token(request: Request) -> None:
    """验证 Bearer token"""
    # 以下端点不需要认证
    public_paths = ["/health", "/", "/pc-config", "/pc-sensor/config", "/pc-sensor/status"]
    if request.url.path in public_paths:
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization 头，格式: Bearer {token}")

    token = auth_header[7:]
    if token != AGENT_TOKEN:
        raise HTTPException(status_code=401, detail="Token 无效")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """认证中间件 - 对所有请求验证 token"""
    try:
        await verify_token(request)
    except HTTPException:
        return JSONResponse(
            status_code=401,
            content={"detail": "未授权访问，请提供有效的 Bearer token"},
        )
    except Exception as e:
        logger.error("认证中间件异常: %s", e)
        return JSONResponse(
            status_code=500,
            content={"detail": "认证服务内部错误"},
        )
    return await call_next(request)


# ============================================================
# Pydantic 请求模型
# ============================================================


class FileWriteRequest(BaseModel):
    """文件写入请求"""
    path: str
    content: str


class ExecRequest(BaseModel):
    """命令执行请求"""
    command: str
    timeout: Optional[int] = 30


# ============================================================
# API 端点
# ============================================================


@app.get("/health")
async def health():
    """健康检查端点 - 不需要 token 认证"""
    return {
        "status": "ok",
        "agent_id": config.get("agent_id", "default-agent"),
        "agent_name": config.get("agent_name", "我的电脑"),
    }


@app.get("/screenshot")
async def screenshot():
    """截取屏幕截图，返回 PNG 二进制图像"""
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")
    except ImportError:
        raise HTTPException(status_code=500, detail="PIL 未安装，无法截图")
    except Exception as e:
        logger.error("截图失败: %s", e)
        raise HTTPException(status_code=500, detail=f"截图失败: {str(e)}")


@app.get("/files/list")
async def list_files(path: str = "C:\\"):
    """
    列出指定路径下的文件和目录

    注意: 某些路径需要管理员权限才能访问。
    """
    if is_path_blocked(path):
        raise HTTPException(status_code=403, detail="禁止访问该路径")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"路径不存在: {path}")

    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"不是目录: {path}")

    try:
        entries = []
        for entry in os.scandir(path):
            try:
                is_dir = entry.is_dir()
                info = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if is_dir else "file",
                    "size": info.st_size if not is_dir else 0,
                    "modified": datetime.fromtimestamp(info.st_mtime).isoformat(),
                })
            except (PermissionError, OSError):
                # 无权限访问的文件/目录，仍然返回基本信息
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir(follow_symlinks=False) else "file",
                    "size": 0,
                    "modified": "",
                })

        # 目录排在前面，然后按名称排序
        entries.sort(key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].lower()))
        return entries
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"无权限访问该路径: {path}")
    except Exception as e:
        logger.error("列出目录失败: %s", e)
        raise HTTPException(status_code=500, detail=f"列出目录失败: {str(e)}")


@app.get("/files/read")
async def read_file(path: str = "C:\\"):
    """读取文件内容（最大 1MB）"""
    if is_path_blocked(path):
        raise HTTPException(status_code=403, detail="禁止访问该路径")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"不是文件: {path}")

    try:
        # 检查文件大小
        file_size = os.path.getsize(path)
        max_size = 1 * 1024 * 1024  # 1MB
        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，超过 1MB 限制",
            )

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return {"content": content, "size": file_size, "encoding": "utf-8"}
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"无权限读取文件: {path}")
    except UnicodeDecodeError:
        # 尝试二进制读取并返回 base64 或提示
        raise HTTPException(status_code=400, detail="无法以文本方式读取该文件（可能是二进制文件）")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("读取文件失败: %s", e)
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")


@app.post("/files/write")
async def write_file(req: FileWriteRequest):
    """写入文件内容"""
    if is_path_blocked(req.path):
        raise HTTPException(status_code=403, detail="禁止访问该路径")

    try:
        # 确保目标目录存在
        target_dir = os.path.dirname(req.path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        with open(req.path, "w", encoding="utf-8") as f:
            f.write(req.content)

        logger.info("文件写入成功: %s (%d 字节)", req.path, len(req.content))
        return {"success": True, "path": req.path, "size": len(req.content)}
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"无权限写入文件: {req.path}")
    except Exception as e:
        logger.error("写入文件失败: %s", e)
        raise HTTPException(status_code=500, detail=f"写入文件失败: {str(e)}")


@app.post("/exec")
async def execute_command(req: ExecRequest):
    """执行系统命令并返回结果"""
    if is_command_blocked(req.command):
        raise HTTPException(status_code=403, detail=f"禁止执行危险命令: {req.command}")

    try:
        result = subprocess.run(
            req.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=req.timeout,
        )

        # 尽量确保输出以 UTF-8 编码解码
        stdout = result.stdout
        stderr = result.stderr

        # 尝试修复编码（Windows 可能输出 GBK）
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        return {
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail=f"命令执行超时 ({req.timeout}秒)")
    except subprocess.SubprocessError as e:
        logger.error("命令执行失败: %s", e)
        raise HTTPException(status_code=500, detail=f"命令执行失败: {str(e)}")
    except Exception as e:
        logger.error("命令执行异常: %s", e)
        raise HTTPException(status_code=500, detail=f"命令执行异常: {str(e)}")


@app.get("/system/info")
async def system_info():
    """获取系统信息"""
    try:
        import psutil

        mem = psutil.virtual_memory()
        cpu_freq = psutil.cpu_freq()

        info: dict[str, Any] = {
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()} {platform.version()}",
            "os_arch": platform.machine(),
            "cpu": {
                "model": platform.processor() or "Unknown",
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "freq_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
                "usage_percent": psutil.cpu_percent(interval=0.1),
            },
            "memory": {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "usage_percent": mem.percent,
            },
            "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        }

        # 收集磁盘信息
        disk_info: dict[str, dict[str, Any]] = {}
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disk_info[part.mountpoint] = {
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "usage_percent": usage.percent,
                    "fstype": part.fstype,
                }
            except PermissionError:
                pass
        info["disk"] = disk_info

        return info
    except ImportError:
        # 没有 psutil 时降级返回基本信息
        return _system_info_fallback()
    except Exception as e:
        logger.error("获取系统信息失败: %s", e)
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")


def _system_info_fallback() -> dict[str, Any]:
    """psutil 不可用时的降级方案"""
    mem_total = 0
    mem_available = 0
    try:
        # 尝试通过命令获取内存信息
        result = subprocess.run(
            "wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /format:csv",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split(",")
            if len(parts) >= 3:
                mem_total = int(parts[1]) // 1024  # KB -> MB
                mem_available = int(parts[2]) // 1024
    except Exception:
        pass

    return {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "os_arch": platform.machine(),
        "cpu": {
            "model": platform.processor() or "Unknown",
            "info": "安装 psutil 获取详细 CPU 信息",
        },
        "memory": {
            "total_gb": round(mem_total / 1024, 2) if mem_total else 0,
            "available_gb": round(mem_available / 1024, 2) if mem_available else 0,
            "note": "安装 psutil 获取精确内存信息",
        },
    }


# ============================================================
# PC 感知采集器 API
# ============================================================

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/", include_in_schema=False)
@app.get("/pc-config", include_in_schema=False)
async def serve_pc_config_page():
    """PC 感知配置页面"""
    html_path = os.path.join(STATIC_DIR, "pc_config.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>PC 感知配置</h1><p>页面文件未找到</p>")


@app.get("/pc-sensor/config")
async def get_pc_sensor_config():
    """获取 PC 感知配置"""
    return pc_sensor_manager.config


@app.post("/pc-sensor/config")
async def update_pc_sensor_config(data: dict):
    """更新 PC 感知配置"""
    old_enabled = pc_sensor_manager.config.get("enabled", False)
    new_cfg = pc_sensor_manager.update_config(data)
    new_enabled = new_cfg.get("enabled", False)

    # 启用/禁用状态变化时启停采集器
    if old_enabled != new_enabled:
        if new_enabled:
            pc_sensor_manager.start()
        else:
            pc_sensor_manager.stop()
    elif new_enabled and not pc_sensor_manager.running:
        # 如果已启用但未运行（如启动时未启用，后来手动启用了）
        pc_sensor_manager.start()

    return {"success": True, "config": new_cfg}


@app.get("/pc-sensor/status")
async def get_pc_sensor_status():
    """获取 PC 感知运行状态"""
    return pc_sensor_manager.get_status()


# ============================================================
# WebSocket 命令处理函数
# ============================================================


def handle_screenshot(params: dict) -> dict:
    """处理截图命令（WS 调用）"""
    try:
        from PIL import ImageGrab
        import base64
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {"base64": base64.b64encode(buf.getvalue()).decode()}
    except Exception as e:
        logger.error("截图失败: %s", e)
        return {"error": str(e)}


def handle_file_list(params: dict) -> dict:
    """处理文件列表命令（WS 调用）"""
    path = params.get("path", "C:\\")
    if is_path_blocked(path):
        return {"error": "禁止访问该路径"}
    try:
        if not os.path.exists(path):
            return {"error": f"路径不存在: {path}"}
        if not os.path.isdir(path):
            return {"error": f"不是目录: {path}"}
        entries = []
        for entry in os.scandir(path):
            try:
                is_dir = entry.is_dir()
                info = entry.stat()
                entries.append({
                    "name": entry.name,
                    "type": "dir" if is_dir else "file",
                    "size": info.st_size if not is_dir else 0,
                    "modified": datetime.fromtimestamp(info.st_mtime).isoformat(),
                })
            except (PermissionError, OSError):
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir(follow_symlinks=False) else "file",
                    "size": 0,
                    "modified": "",
                })
        entries.sort(key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].lower()))
        return entries
    except Exception as e:
        logger.error("列出目录失败: %s", e)
        return {"error": str(e)}


def handle_file_read(params: dict) -> dict:
    """处理文件读取命令（WS 调用）"""
    path = params.get("path", "")
    if is_path_blocked(path):
        return {"error": "禁止访问该路径"}
    try:
        if not os.path.exists(path):
            return {"error": f"文件不存在: {path}"}
        if not os.path.isfile(path):
            return {"error": f"不是文件: {path}"}
        # 限制 1MB
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(1024 * 1024)
        return {"content": content}
    except PermissionError:
        return {"error": "无权限读取文件"}
    except Exception as e:
        logger.error("读取文件失败: %s", e)
        return {"error": str(e)}


def handle_file_write(params: dict) -> dict:
    """处理文件写入命令（WS 调用）"""
    path = params.get("path", "")
    content = params.get("content", "")
    if is_path_blocked(path):
        return {"error": "禁止访问该路径"}
    try:
        target_dir = os.path.dirname(path)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("文件写入成功: %s (%d 字节)", path, len(content))
        return {"success": True, "path": path, "size": len(content)}
    except PermissionError:
        return {"error": "无权限写入文件"}
    except Exception as e:
        logger.error("写入文件失败: %s", e)
        return {"error": str(e)}


def handle_exec(params: dict) -> dict:
    """处理命令执行命令（WS 调用）"""
    command = params.get("command", "")
    timeout = params.get("timeout", 30)
    if is_command_blocked(command):
        return {"error": "禁止执行危险命令"}
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout
        stderr = result.stderr
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"命令执行超时({timeout}s)"}
    except Exception as e:
        logger.error("命令执行失败: %s", e)
        return {"error": str(e)}


def handle_system_info(params: dict) -> dict:
    """处理系统信息命令（WS 调用）"""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "os_arch": platform.machine(),
            "cpu": {
                "model": platform.processor() or "Unknown",
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=0.1),
            },
            "memory": {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "usage_percent": mem.percent,
            },
        }
    except ImportError:
        return _system_info_fallback()
    except Exception as e:
        logger.error("获取系统信息失败: %s", e)
        return {"error": str(e)}


# ============================================================
# WebSocket 客户端
# ============================================================


async def websocket_client():
    """WebSocket 客户端，连接到服务器 /ws/agent"""
    server_url = config.get("server_url", "")
    agent_token = config.get("agent_token", "")

    if not server_url:
        logger.info("WebSocket 客户端未配置 server_url，跳过")
        return

    logger.info("WebSocket 客户端启动，连接目标: %s", server_url)

    # 自签名证书跳过验证（仅wss需要）
    import ssl
    ws_ssl = None
    if server_url.startswith("wss://"):
        ws_ssl = ssl.create_default_context()
        ws_ssl.check_hostname = False
        ws_ssl.verify_mode = ssl.CERT_NONE

    while True:
        try:
            kwargs = {"ping_interval": 30, "ping_timeout": 10}
            if ws_ssl is not None:
                kwargs["ssl"] = ws_ssl
            async with websockets.connect(server_url, **kwargs) as ws:
                logger.info("已连接到服务器")

                # 1. 注册
                await ws.send(json.dumps({
                    "type": "register",
                    "agent_id": config.get("agent_id", "default-agent"),
                    "agent_name": config.get("agent_name", "我的电脑"),
                    "capabilities": ["screenshot", "file", "exec", "system_info"],
                }))
                logger.info("已发送注册请求")

                # 等待注册确认
                resp = json.loads(await ws.recv())
                if resp.get("type") == "registered":
                    logger.info("注册成功: %s", resp.get("agent_id"))

                # 2. 心跳任务
                async def heartbeat_loop():
                    """每 30 秒发送一次心跳"""
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send(json.dumps({"type": "heartbeat"}))
                        except Exception:
                            break

                heartbeat_task = asyncio.create_task(heartbeat_loop())

                try:
                    # 3. 命令处理循环
                    async for message in ws:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "cmd":
                            cmd_id = data.get("cmd_id")
                            action = data.get("action")
                            params = data.get("params", {})

                            logger.info("收到命令: %s (cmd_id=%s)", action, cmd_id)

                            handlers = {
                                "screenshot": handle_screenshot,
                                "file_list": handle_file_list,
                                "file_read": handle_file_read,
                                "file_write": handle_file_write,
                                "exec": handle_exec,
                                "system_info": handle_system_info,
                            }

                            handler = handlers.get(action)
                            if handler:
                                result = handler(params)
                                await ws.send(json.dumps({
                                    "type": "result",
                                    "cmd_id": cmd_id,
                                    "data": result,
                                }))
                                logger.info("命令结果已返回: %s", cmd_id)
                            else:
                                await ws.send(json.dumps({
                                    "type": "result",
                                    "cmd_id": cmd_id,
                                    "error": f"未知命令: {action}",
                                }))

                        elif msg_type == "heartbeat_ack":
                            pass  # 心跳确认，无需处理

                finally:
                    heartbeat_task.cancel()

        except websockets.exceptions.ConnectionClosed:
            logger.warning("连接断开，5秒后重连...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("连接异常: %s，5秒后重连...", str(e))
            await asyncio.sleep(5)


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    host = config.get("server_host", "0.0.0.0")
    port = config.get("server_port", 18888)
    token_preview = config.get("agent_token", "未设置")[:8] + "..."

    print("=" * 50)
    print(f"  Axeuh Windows Agent")
    print(f"  服务地址: http://{host}:{port}")
    print(f"  Agent ID: {config.get('agent_id', 'default-agent')}")
    print(f"  Agent名称: {config.get('agent_name', '我的电脑')}")
    print(f"  Token前缀: {token_preview}")
    print("=" * 50)
    print("  API 端点:")
    print(f"  GET  /health       - 健康检查")
    print(f"  GET  /screenshot   - 截取屏幕")
    print(f"  GET  /files/list   - 列出目录")
    print(f"  GET  /files/read   - 读取文件")
    print(f"  POST /files/write  - 写入文件")
    print(f"  POST /exec         - 执行命令")
    print(f"  GET  /system/info  - 系统信息")
    print(f"  GET  /pc-config    - PC 感知配置面板")
    print(f"  GET  /pc-sensor/*  - PC 感知 API")
    print(f"  WS  客户端: {config.get('server_url', '未配置')}")
    print("=" * 50)

    # 启动 PC 感知采集器（如果配置中启用了）
    pc_sensor_manager.start()

    # 启动 WebSocket 客户端（后台线程，因为 uvicorn.run 会阻塞）
    if config.get("server_url"):
        import threading

        ws_thread = threading.Thread(
            target=lambda: asyncio.run(websocket_client()),
            daemon=True,
            name="ws-client",
        )
        ws_thread.start()
        logger.info("WebSocket 客户端已启动（后台线程）")

    # 添加一些启动信息
    if pc_sensor_manager.config.get("enabled", False):
        print(f"  PC 感知: 已启用 (空闲阈值: {pc_sensor_manager.config.get('idle_threshold', 300)}s)")
    else:
        print(f"  PC 感知: 未启用（配置面板: http://localhost:{port}/pc-config）")

    uvicorn.run(app, host=host, port=port)
