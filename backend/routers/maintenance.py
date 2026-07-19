"""
维护管理路由 - 系统维护相关端点
"""

import os
import sys
import asyncio
import subprocess

from fastapi import APIRouter

router = APIRouter(prefix="/api/screen")


@router.post("/restart")
async def restart_backend():
    """重启后端服务

    流程:
    1. 立即返回重启确认消息
    2. 后台等待 0.5 秒（确保响应已发送）
    3. 启动新进程（复用当前命令行参数）
    4. 退出当前进程
    """
    async def _do_restart():
        await asyncio.sleep(0.5)
        # 用相同的 Python 和参数启动新进程
        subprocess.Popen([sys.executable] + sys.argv)
        os._exit(0)

    asyncio.create_task(_do_restart())
    return {"success": True, "message": "后端服务正在重启..."}
