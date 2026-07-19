# -*- coding: utf-8 -*-
"""
数据上传模块

使用后端账号密码登录获取 token，上报感知数据时自动携带 token。
token 有效期为 24 小时，提前 1 小时刷新。
使用 urllib 实现，不依赖外部 HTTP 库。
"""

import json
import logging
import threading
import time
import ssl
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urljoin

logger = logging.getLogger("pc_sensor.uploader")


class Uploader:
    """数据上传器

    启动时先用账号密码登录获取 token，上报数据时自动携带。
    token 过期前自动刷新。
    """

    def __init__(self, server_url: str, username: str, password: str, agent_id: str):
        """
        Args:
            server_url: 后端服务器地址，默认为 https://localhost:8767
            username: 后端登录用户名
            password: 后端登录密码
            agent_id: Agent ID，用于后端标记数据来源
        """
        self.server_url = server_url.rstrip("/")
        self.username = username
        self.password = password
        self.agent_id = agent_id

        self._token: Optional[str] = None
        self._token_expiry: float = 0  # time.monotonic 值
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._flush_interval = 5.0

        # SSL 上下文（处理自签名证书）
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE

        # 启动时登录
        self._login()

    # ---- Token 管理 ----

    def _login(self) -> bool:
        """使用用户名密码登录，获取 Bearer token"""
        if not self.server_url or not self.username or not self.password:
            logger.warning("服务器地址/用户名/密码未配置，无法登录")
            return False

        try:
            payload = json.dumps({
                "username": self.username,
                "password": self.password,
            }, ensure_ascii=False).encode("utf-8")

            url = urljoin(self.server_url, "/login")
            req = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urlopen(req, timeout=10, context=self._ssl_ctx) as resp:
                body = json.loads(resp.read())
                if body.get("success") and body.get("token"):
                    self._token = body["token"]
                    # token 24h 有效，提前 1h 刷新
                    self._token_expiry = time.monotonic() + 23 * 3600
                    logger.info("登录成功（%s），token 已获取", body.get("user_id", ""))
                    return True
                else:
                    logger.warning("登录失败: %s", body.get("message", "未知错误"))
                    return False

        except URLError as e:
            logger.info("登录失败（网络不可达，稍后重试）: %s", e)
            return False
        except Exception as e:
            logger.warning("登录异常: %s", e)
            return False

    def _ensure_token(self):
        """确保 token 有效，需要时重新登录"""
        if not self._token or time.monotonic() >= self._token_expiry:
            self._login()

    def force_relogin(self) -> bool:
        """强制重新登录（供配置界面测试连接用）"""
        self._token = None
        return self._login()

    # ---- 数据上传 ----

    def enqueue(self, data: dict):
        """将一条数据加入发送队列"""
        if not self.server_url:
            return
        with self._lock:
            self._buffer.append(data)

    def flush(self):
        """批量发送队列中所有数据"""
        if not self.server_url:
            return

        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer[:]
            self._buffer.clear()

        self._send_batch(batch)

    @property
    def buffer_size(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def has_token(self) -> bool:
        return self._token is not None

    def _send_batch(self, batch: list[dict]):
        """发送一批数据到后端"""
        self._ensure_token()
        if not self._token:
            logger.debug("无有效 token，丢弃 %d 条数据", len(batch))
            return

        try:
            payload = json.dumps({
                "agent_id": self.agent_id,
                "events": batch,
            }, ensure_ascii=False).encode("utf-8")

            url = urljoin(self.server_url, "/api/pc/sync")
            req = Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                method="POST",
            )

            with urlopen(req, timeout=10, context=self._ssl_ctx) as resp:
                if resp.status == 200:
                    logger.debug("已上报 %d 条 PC 感知数据", len(batch))
                else:
                    logger.warning("上报失败: HTTP %d", resp.status)

        except URLError as e:
            logger.debug("上报失败（网络可恢复）: %s", e)
        except Exception as e:
            logger.warning("上报异常（丢弃 %d 条数据）: %s", len(batch), e)
