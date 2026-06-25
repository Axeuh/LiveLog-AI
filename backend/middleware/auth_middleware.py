"""
认证中间件模块

提供 AuthMiddleware 和 get_current_user_id 函数，
用于多用户 Token 认证和用户 ID 注入。
"""

from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from auth import verify_token


# 不需要认证的路径
PUBLIC_PATHS = [
    "/",
    "/api/health/query",
    "/api/mobile/dashboard",
    "/api/mobile/files",
    "/api/mobile/files/content",
    "/api/mobile/files/raw",
    "/api/mobile/reports",
    "/api/mobile/session/create",
    "/api/mobile/session/list",
    "/api/mobile/session/message",
    "/api/mobile/session/switch",
    "/api/ota/check",
    "/api/ota/download",
    "/api/ota/info",
    "/api/screen/events/stream",
    "/api/screen/session/create",
    "/api/screen/session/list",
    "/api/screen/session/message",
    "/api/screen/session/switch",
    "/api/screen/stt/continue-chat",
    "/api/screen/stt/recognize-file",
    "/docs",
    "/favicon.ico",
    "/health",
    "/login",
    "/mobile",
    "/mobile/",
    "/openapi.json",
    "/redoc",
    "/ws/voice-assistant",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 检查是否是公开路径
        if path in PUBLIC_PATHS or path.startswith("/docs") or path.startswith("/openapi"):
            return await call_next(request)

        # 检查是否是静态文件
        if path.startswith("/static") or path.endswith((".js", ".css", ".html", ".png", ".ico")):
            return await call_next(request)

        # Phase 2: 不再有 localhost 绕过 - 所有请求均需 Token 认证

        # 公网访问需要Token认证
        auth_header = request.headers.get("Authorization", "")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # 也支持查询参数传递token（用于WebSocket）
        if not token:
            token = request.query_params.get("token") or ""

        is_valid, user_id = verify_token(token)
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，请先登录"}
            )

        request.state.user_id = user_id  # 注入 user_id
        return await call_next(request)


def get_current_user_id(request: Request) -> Optional[str]:
    """获取当前请求的用户ID"""
    return getattr(request.state, 'user_id', None)
