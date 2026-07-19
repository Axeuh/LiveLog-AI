"""
统一配置模块 - 所有服务从此文件读取配置

支持通过环境变量 CONFIG_PATH 或 launcher.py --config 指定自定义 YAML 路径。
从 config.yaml 加载，提供类型安全的 getter 函数。
"""
import os
import sys
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, Optional

import yaml


_CONFIG_PATH = os.environ.get('CONFIG_PATH')  # 优先环境变量，也可由 launcher.py --config 覆盖


def set_config_path(path: str):
    """设置自定义配置文件路径（launcher.py 传入）"""
    global _CONFIG_PATH
    _CONFIG_PATH = path


def _resolve_base() -> Path:
    """
    返回项目根目录（backend/ 的父目录）。
    默认: backend/config/config.py → backend/config/ → backend/ → 项目根 (3级)
    自定义: pzn/backend/config/config.yaml → pzn/backend/config/ → pzn/backend/ → pzn/ (3级)
    """
    if _CONFIG_PATH:
        return Path(_CONFIG_PATH).parent.parent.parent
    return Path(__file__).parent.parent.parent


def _load_yaml() -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    if _CONFIG_PATH:
        yaml_path = Path(_CONFIG_PATH)
    else:
        # 优先 backend/config/config.yaml，回退到项目根目录 config.yaml
        yaml_path = Path(__file__).parent / 'config.yaml'
        if not yaml_path.exists():
            yaml_path = _resolve_base() / 'config.yaml'
    if not yaml_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {yaml_path}")
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class Config:
    """配置类，提供类型安全的配置访问"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    # ── 服务端口 ─────────────────────────────────────

    @property
    def BACKEND_HOST(self) -> str:
        return self._data.get('server', {}).get('host', '0.0.0.0')

    @property
    def BACKEND_HTTPS_PORT(self) -> int:
        return self._data.get('server', {}).get('https_port', 8767)

    @property
    def BACKEND_HTTP_PORT(self) -> int:
        return self._data.get('server', {}).get('http_port', 8768)

    @property
    def BACKEND_PORT(self) -> int:
        return self.BACKEND_HTTPS_PORT

    # ── OpenCode ─────────────────────────────────────

    @property
    def OPENCODE_URL(self) -> str:
        return self._data.get('opencode', {}).get('url', 'http://127.0.0.1:4096')

    @property
    def OPENCODE_DIRECTORY(self) -> str:
        """OpenCode 实例目录（发送到 x-opencode-directory 头）"""
        raw = self._data.get('opencode', {}).get('directory', 'ai')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def OPENCODE_PORT(self) -> int:
        url = self.OPENCODE_URL
        if ':' in url:
            try:
                return int(url.split(':')[-1].rstrip('/'))
            except (ValueError, IndexError):
                pass
        return 4096

    @property
    def OPENCODE_HOST(self) -> str:
        return 'localhost'

    @property
    def OPENCODE_DEFAULT_MODEL(self) -> str:
        return self._data.get('opencode', {}).get('default_model', 'claude-sonnet-4-20250514')

    @property
    def OPENCODE_DEFAULT_PROVIDER(self) -> str:
        return self._data.get('opencode', {}).get('default_provider', 'anthropic')

    # ── 功能开关 ─────────────────────────────────────

    @property
    def OPENCODE_MOCK_ENABLED(self) -> bool:
        return bool(self._data.get('features', {}).get('opencode_mock_enabled', False))

    # ── SSL ──────────────────────────────────────────

    @property
    def SSL_ENABLED(self) -> bool:
        """SSL/HTTPS 开关"""
        return bool(self._data.get('ssl', {}).get('enabled', True))

    @property
    def SSL_CERT(self) -> str:
        return self._data.get('ssl', {}).get('cert', '')

    @property
    def SSL_KEY(self) -> str:
        return self._data.get('ssl', {}).get('key', '')

    # ── API ──────────────────────────────────────────

    @property
    def DASHSCOPE_KEY(self) -> str:
        return self._data.get('api', {}).get('dashscope_key', '')

    @property
    def MIMO_API_KEY(self) -> str:
        return self._data.get('api', {}).get('mimo_key', '')

    # ── 认证 ─────────────────────────────────────────

    @property
    def AUTH_USERNAME(self) -> str:
        return self._data.get('auth', {}).get('username', 'Axeuh')

    @property
    def AUTH_PASSWORD_HASH(self) -> str:
        return self._data.get('auth', {}).get('password_hash', '')

    # ── 启动器路径 ───────────────────────────────────

    @property
    def CONDAPYTHON_PATH(self) -> str:
        return self._data.get('launcher', {}).get('conda_python', 'python')

    @property
    def OPENCODE_CMD_PATH(self) -> str:
        return self._data.get('launcher', {}).get('opencode_cmd', 'opencode')

    # ── 智能体 ───────────────────────────────────────

    @property
    def DEFAULT_AGENT_TYPE(self) -> str:
        return self._data.get('agent', {}).get('default_type', 'explore')

    @property
    def AVAILABLE_AGENTS(self) -> str:
        agents = self._data.get('agent', {}).get('available', ['explore'])
        return ','.join(agents) if isinstance(agents, list) else str(agents)

    # ── 日志 ─────────────────────────────────────────

    @property
    def LOG_LEVEL(self) -> str:
        return self._data.get('log', {}).get('level', 'INFO')

    # ── 记忆系统 ─────────────────────────────────────

    @property
    def MEMORY_SEARCH_THRESHOLD(self) -> float:
        return float(self._data.get('memory', {}).get('search_threshold', 0.7))

    @property
    def MEMORY_SEARCH_LIMIT(self) -> int:
        return int(self._data.get('memory', {}).get('search_limit', 10))

    # ── 数据目录 ─────────────────────────────────────
    # 所有运行时路径基于项目根目录，支持绝对路径覆盖

    @property
    def DATA_DIR(self) -> str:
        """数据存储根目录，默认 backend/data"""
        raw = self._data.get('data', {}).get('dir', 'backend/data')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def SESSIONS_PATH(self) -> str:
        """用户会话列表 JSON 路径"""
        raw = self._data.get('data', {}).get('sessions', 'backend/usersessions.json')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def VOICEPRINTS_PATH(self) -> str:
        raw = self._data.get('data', {}).get('voiceprints', 'backend/data/voiceprints.json')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def HEALTH_DIR(self) -> str:
        # 健康数据与感知数据同目录（ai/data/{date}/health.json）
        return self.DATA_DIR

    @property
    def AUDIO_DIR(self) -> str:
        return os.path.join(self.DATA_DIR, 'audio')

    @property
    def UPLOAD_DIR(self) -> str:
        """用户上传文件存储目录，默认 ai/data/uploads"""
        raw = self._data.get('data', {}).get('upload_dir', 'ai/data/uploads')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def AI_ROOT(self) -> str:
        """文件浏览根目录（ai/），用于手机页文件浏览器"""
        raw = self._data.get('data', {}).get('ai_root', '')
        if raw:
            if os.path.isabs(raw):
                return raw
            return str(_resolve_base() / raw)
        # 向后兼容：从 DATA_DIR 的父目录推算
        return str(Path(self.DATA_DIR).parent)

    @property
    def TASKS_DIR(self) -> str:
        """定时任务数据目录，默认 ai/data"""
        raw = self._data.get('data', {}).get('tasks', 'ai/data')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def SCRIPTS_DIR(self) -> str:
        """自定义脚本目录，默认 ai/data/tasks（与 YAML 任务同目录）"""
        raw = self._data.get('scripts', {}).get('dir', 'ai/data/tasks')
        if os.path.isabs(raw):
            return raw
        return str(_resolve_base() / raw)

    @property
    def OTA_APK_DIR(self) -> str:
        """APK 构建输出目录"""
        return self._data.get('ota', {}).get('apk_dir', os.path.join(str(_resolve_base()), 'app', 'build', 'outputs', 'apk', 'debug'))


@lru_cache()
def get_config() -> Config:
    """获取全局配置单例"""
    data = _load_yaml()
    return Config(data)
