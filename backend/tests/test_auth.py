# -*- coding: utf-8 -*-
"""
认证模块测试

覆盖场景：
  - 正确/错误密码登录
  - Token 认证检查
  - 登出后 token 失效
  - 本地访问不再免认证（Phase 2 已移除）
  - 公开路径（OTA/health/login/docs）无需 token
"""
import pytest
from config.config import get_config

# 从配置读取端口，避免硬编码
_TEST_HOST = f"localhost:{get_config().BACKEND_HTTPS_PORT}"


class TestLogin:
    """登录功能"""

    def test_login_success(self, client):
        """POST /login 正确凭据应返回 token"""
        resp = client.post("/login", json={
            "username": "Axeuh",
            "password": "20071011"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["token"] is not None
        assert len(data["token"]) > 0
        assert data["user_id"] == "Axeuh"
        assert data["display_name"] is not None

    def test_login_fail_wrong_password(self, client):
        """POST /login 错误密码应返回 success=False"""
        resp = client.post("/login", json={
            "username": "Axeuh",
            "password": "wrong_password_123"
        })
        assert resp.status_code == 200  # 登录端点总是返回 200
        data = resp.json()
        assert data["success"] is False
        assert data["token"] is None

    def test_login_fail_wrong_username(self, client):
        """POST /login 不存在的用户名应返回 success=False"""
        resp = client.post("/login", json={
            "username": "NonExistentUser",
            "password": "any_password"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


class TestAuthCheck:
    """认证状态检查"""

    def test_auth_check_valid_token(self, client, auth_headers):
        """GET /auth/check 有效 token 应返回 authenticated=True"""
        resp = client.get("/auth/check", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True
        assert data["user_id"] == "Axeuh"

    def test_auth_check_no_token(self, client):
        """
        GET /auth/check 无 token 时 AuthMiddleware 返回 401。
        注意：/auth/check 端点本身可以处理无 token 场景，
        但 AuthMiddleware 在非 localhost 请求时会先拦截。
        """
        resp = client.get("/auth/check")
        assert resp.status_code == 401

    def test_auth_check_invalid_token(self, client):
        """
        GET /auth/check 无效 token 时 AuthMiddleware 返回 401。
        """
        resp = client.get(
            "/auth/check",
            headers={"Authorization": "Bearer invalid_token_xxx"}
        )
        assert resp.status_code == 401


class TestLogout:
    """登出功能"""

    def test_logout_success(self, client, auth_headers):
        """POST /logout 应成功使 token 失效"""
        # 先验证 token 有效
        check1 = client.get("/auth/check", headers=auth_headers)
        assert check1.json()["authenticated"] is True

        # 登出
        resp = client.post("/logout", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # 登出后 token 失效 → AuthMiddleware 返回 401
        check2 = client.get("/auth/check", headers=auth_headers)
        assert check2.status_code == 401

    def test_logout_no_token(self, client):
        """POST /logout 无 token 被 AuthMiddleware 拦截返回 401"""
        resp = client.post("/logout")
        assert resp.status_code == 401


class TestLocalAuthBypass:
    """本地访问认证"""

    def test_localhost_no_longer_bypasses_auth(self, client):
        """
        使用 localhost Host 头访问受保护端点应返回 401。
        Phase 2 已移除所有 localhost 认证绕过。
        """
        resp = client.get(
            "/api/screen/tasks",
            headers={"host": "localhost:9787"}
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "detail" in data

    def test_127_dot_0_dot_0_dot_1_requires_auth(self, client):
        """
        使用 127.0.0.1 Host 头访问受保护端点应返回 401。
        """
        resp = client.get(
            "/api/screen/tasks",
            headers={"host": "127.0.0.1:9787"}
        )
        assert resp.status_code == 401

    def test_non_localhost_requires_auth(self, client):
        """
        非 localhost Host 头访问受保护端点应返回 401。
        TestClient 默认 Host 为 "testserver"，触发认证中间件。
        """
        resp = client.get("/api/screen/components")
        assert resp.status_code == 401
        data = resp.json()
        assert "detail" in data


class TestPublicPaths:
    """公开路径无需 Token"""

    def test_health_no_token(self, client):
        """GET /health 无需 token"""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_login_no_token(self, client):
        """POST /login 无需 token"""
        resp = client.post("/login", json={
            "username": "Axeuh",
            "password": "20071011"
        })
        assert resp.status_code == 200

    def test_ota_check_no_token(self, client):
        """GET /api/ota/check 无需 token（PUBLIC_PATHS）"""
        resp = client.get("/api/ota/check")
        # OTA 端点可能返回 200 或 404（取决于 OTA 路由是否注册）
        # 只要不是 401 就算通过
        assert resp.status_code != 401

    def test_valid_token_allows_access(self, client, auth_headers):
        """有效 token 可访问受保护端点"""
        resp = client.get("/auth/check", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["authenticated"] is True

    def test_docs_no_token(self, client):
        """GET /docs 无需 token"""
        resp = client.get("/docs")
        assert resp.status_code == 200
