# -*- coding: utf-8 -*-
"""
认证 API 路由 — 登录/登出/认证检查
"""
from fastapi import APIRouter, Request
from auth import LoginRequest, LoginResponse, verify_password, create_token, verify_token, logout, get_auth_config

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """登录"""
    is_valid, user_id = verify_password(request.username, request.password)
    if is_valid and user_id:
        token = create_token(user_id)
        config = get_auth_config()
        display_name = config.users[user_id].display_name
        return LoginResponse(success=True, token=token, user_id=user_id, display_name=display_name, message="登录成功")
    else:
        return LoginResponse(success=False, message="用户名或密码错误")


@router.post("/logout")
async def logout_endpoint(request: Request):
    """登出"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        logout(token)
    return {"success": True, "message": "已登出"}


@router.get("/auth/check")
async def auth_check(request: Request):
    """检查认证状态"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        is_valid, user_id = verify_token(token)
        if is_valid:
            return {"authenticated": True, "user_id": user_id}
    return {"authenticated": False}
