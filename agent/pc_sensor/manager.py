# -*- coding: utf-8 -*-
"""
PC 感知采集管理器

统一管理各采集器的生命周期和主循环调度。
在后台线程中运行，通过回调接收采集事件并上传。
"""

import os
import time
import json
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from .window_tracker import WindowTracker, get_foreground_window, WindowInfo
from .idle_tracker import IdleTracker, get_idle_seconds, is_screen_locked
from .uploader import Uploader

logger = logging.getLogger("pc_sensor.manager")

CST = timezone(timedelta(hours=8))

# 默认配置
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "server_url": "",
    "username": "",
    "password": "",
    "idle_threshold": 300,
    "window_enabled": True,
    "idle_enabled": True,
    "screen_enabled": True,
}


def _ensure_config(config_path: str) -> dict[str, Any]:
    """确保 pc_sensor_config.json 存在，返回配置"""
    if not config_path:
        return dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            return dict(DEFAULT_CONFIG)
    except Exception as e:
        logger.warning("读取 PC 感知配置失败: %s", e)
        return dict(DEFAULT_CONFIG)


class SensorManager:
    """PC 感知采集管理器

    负责：
    - 加载/保存配置
    - 启动/停止各采集器
    - 在主循环中调度各采集器的 tick()
    - 通过 Uploader 将数据上报到后端
    """

    def __init__(self, config_path: str = ""):
        """
        Args:
            config_path: pc_sensor_config.json 路径
        """
        self.config_path = config_path
        self._cfg = _ensure_config(config_path)

        self._init_uploader()

        self.window_tracker = WindowTracker(on_change=self._on_window_change)
        self.idle_tracker = IdleTracker(
            idle_threshold=self._cfg.get("idle_threshold", 300),
            on_idle=self._on_idle,
            on_active=self._on_active,
            on_screen_change=self._on_screen_change,
        )

        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _init_uploader(self):
        """根据配置创建 Uploader 实例"""
        self.uploader = Uploader(
            server_url=self._cfg.get("server_url") or os.environ.get("AGENT_SERVER_URL", ""),
            username=self._cfg.get("username", ""),
            password=self._cfg.get("password", ""),
            agent_id=self._cfg.get("agent_id", "default-agent"),
        )

    # ---- 配置读写 ----

    @property
    def config(self) -> dict[str, Any]:
        c = dict(self._cfg)
        # 返回配置时隐藏密码
        if c.get("password"):
            c["password"] = "******"
        return c

    def update_config(self, new_cfg: dict[str, Any]) -> dict[str, Any]:
        """更新配置并保存"""
        # 如果传入了 "******" 表示密码未修改，保留原值
        if new_cfg.get("password") == "******":
            new_cfg.pop("password")

        self._cfg.update(new_cfg)

        # 同步到各组件
        self._init_uploader()
        self.idle_tracker.idle_threshold = self._cfg.get("idle_threshold", 300)

        # 持久化
        if self.config_path:
            try:
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self._cfg, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.warning("保存配置失败: %s", e)

        return self.config

    # ---- 生命周期 ----

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        """启动所有采集器（后台线程）"""
        if self._running:
            logger.info("PC 采集管理器已在运行")
            return

        enabled = self._cfg.get("enabled", False)
        if not enabled:
            logger.info("PC 感知采集未启用（可在配置中开启）")
            return

        # 检查登录状态
        if not self.uploader.has_token:
            logger.info("尚未登录，尝试登录...")
            self.uploader.force_relogin()

        if not self.uploader.has_token:
            logger.warning("无法登录，采集器暂不启动。请检查用户名密码和服务器地址")
            return

        self._running = True

        if self._cfg.get("window_enabled", True):
            self.window_tracker.start()
        if self._cfg.get("idle_enabled", True) or self._cfg.get("screen_enabled", True):
            self.idle_tracker.start()

        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="pc-sensor")
        self._thread.start()
        logger.info("PC 采集管理器已启动 (idle_threshold=%ds)", self.idle_tracker.idle_threshold)

    def stop(self):
        """停止所有采集器"""
        self._running = False
        self.window_tracker.stop()
        self.idle_tracker.stop()
        self.uploader.flush()
        logger.info("PC 采集管理器已停止")

    def get_status(self) -> dict[str, Any]:
        """获取运行状态"""
        return {
            "running": self._running,
            "enabled": self._cfg.get("enabled", False),
            "logged_in": self.uploader.has_token,
            "window": self.window_tracker.running,
            "idle": self.idle_tracker.running,
            "last_events": self._last_events,
            "queue_size": self.uploader.buffer_size,
        }

    # ---- 主循环 ----

    def _run_loop(self):
        """采集主循环"""
        last_window = 0.0
        last_idle = 0.0
        last_upload = 0.0

        while self._running:
            now = time.monotonic()

            if self._cfg.get("window_enabled", True) and now - last_window >= 1.0:
                self.window_tracker.tick()
                last_window = now

            if (self._cfg.get("idle_enabled", True) or self._cfg.get("screen_enabled", True)) \
                    and now - last_idle >= 2.0:
                self.idle_tracker.tick()
                last_idle = now

            if now - last_upload >= 5.0:
                self.uploader.flush()
                last_upload = now

            time.sleep(0.2)

        self.uploader.flush()

    # ---- 事件回调 ----

    _last_events: list[dict[str, Any]] = []
    _MAX_EVENTS = 50

    def _record_event(self, data: dict[str, Any]):
        self._last_events.append(data)
        if len(self._last_events) > self._MAX_EVENTS:
            self._last_events = self._last_events[-self._MAX_EVENTS:]

    def _on_window_change(self, win: WindowInfo):
        data = {
            "type": "pc_window",
            "t": datetime.now(CST).strftime("%H:%M:%S"),
            "t_iso": datetime.now(CST).isoformat(),
            "payload": {
                "process": win.process,
                "title": win.title[:200] if win.title else "",
                "pid": win.pid,
            },
        }
        self.uploader.enqueue(data)
        self._record_event(data)
        logger.info("窗口变化: %s - %s", win.process, win.title[:60])

    def _on_idle(self, idle_seconds: int):
        data = {
            "type": "pc_idle",
            "t": datetime.now(CST).strftime("%H:%M:%S"),
            "t_iso": datetime.now(CST).isoformat(),
            "payload": {
                "state": "idle",
                "idle_seconds": idle_seconds,
            },
        }
        self.uploader.enqueue(data)
        self._record_event(data)
        logger.info("无人状态: 已空闲 %d 秒", idle_seconds)

    def _on_active(self):
        data = {
            "type": "pc_idle",
            "t": datetime.now(CST).strftime("%H:%M:%S"),
            "t_iso": datetime.now(CST).isoformat(),
            "payload": {
                "state": "active",
                "idle_seconds": 0,
            },
        }
        self.uploader.enqueue(data)
        self._record_event(data)
        logger.info("用户恢复使用")

    def _on_screen_change(self, locked: bool):
        data = {
            "type": "pc_screen",
            "t": datetime.now(CST).strftime("%H:%M:%S"),
            "t_iso": datetime.now(CST).isoformat(),
            "payload": {
                "state": "lock" if locked else "unlock",
            },
        }
        self.uploader.enqueue(data)
        self._record_event(data)
        logger.info("屏幕%s", "锁定" if locked else "解锁")
