"""
OpenCode Client - OpenCode API交互客户端

功能：
- 创建/切换/列表会话
- 发送消息到OpenCode (使用prompt_async)
- 中止当前任务
- 消息格式封装
"""

import aiohttp
import asyncio
import json
import logging
from datetime import datetime
import os
import fnmatch
import socket
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import base64
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# OpenCode配置
from config.config import get_config
OPENCODE_CONFIG_URL = get_config().OPENCODE_URL
OPENCODE_DEFAULT_DIRECTORY = get_config().OPENCODE_DIRECTORY
OPENCODE_DEFAULT_AGENT = "voice-interaction"  # 使用项目配置中定义的 agent

# OPENCODE_BASE_URL 在模块加载后由 discover_opencode_url() 重写为探测到的可用端口
OPENCODE_BASE_URL = OPENCODE_CONFIG_URL
OPENCODE_DEFAULT_MODEL = "deepseek-v4-flash"
OPENCODE_DEFAULT_PROVIDER = "deepseek"
# 默认模型/提供商，将被配置文件懒加载覆盖（若加载失败，则使用此默认值）
OPENCODE_DEFAULT_MODEL = "k2p5"
OPENCODE_DEFAULT_PROVIDER = "kimi-for-coding"

# ============ 端口自动发现 ============

_OPENCODE_DISCOVERED_URL: Optional[str] = None


def _probe_tcp_port(host: str, port: int, timeout: float = 0.3) -> bool:
    """同步探测 TCP 端口是否开放（超时短，避免阻塞启动）"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def discover_opencode_url(max_offset: int = 10) -> str:
    """
    探测 OpenCode 实际端口（从配置端口开始逐+1）
    
    当默认端口被幽灵进程占用时，自动切换到下一个可用端口。
    结果会缓存并更新全局 OPENCODE_BASE_URL，避免重复探测。
    
    Args:
        max_offset: 最大尝试偏移量（默认 +10）
        
    Returns:
        发现的有效 URL，未发现则返回配置默认值
    """
    global _OPENCODE_DISCOVERED_URL, OPENCODE_BASE_URL
    if _OPENCODE_DISCOVERED_URL is not None:
        return _OPENCODE_DISCOVERED_URL
    
    parsed = urlparse(OPENCODE_CONFIG_URL)
    base_port = parsed.port or 5096
    host = parsed.hostname or "127.0.0.1"
    scheme = parsed.scheme or "http"
    
    for offset in range(max_offset):
        port = base_port + offset
        if _probe_tcp_port(host, port):
            url = f"{scheme}://{host}:{port}"
            if offset > 0:
                logger.warning(
                    f"OpenCode 默认端口 {base_port} 不可用，"
                    f"发现端口 {port}，自动切换至: {url}"
                )
            _OPENCODE_DISCOVERED_URL = url
            OPENCODE_BASE_URL = url  # 更新全局引用
            return url
    
    logger.warning(
        f"OpenCode 端口 {base_port}~{base_port + max_offset - 1} 均无响应，"
        f"使用配置默认: {OPENCODE_CONFIG_URL}"
    )
    _OPENCODE_DISCOVERED_URL = OPENCODE_CONFIG_URL
    return OPENCODE_CONFIG_URL


# 运行时配置缓存
_model_config_loaded = False
_model_config_excluded: List[str] = []
_model_config_data: Dict[str, Any] | None = None


def load_model_config() -> Dict[str, Any]:
    """懒加载模型配置，供默认模型/提供商及排除列表使用"""
    global _model_config_loaded, _model_config_excluded, _model_config_data
    global OPENCODE_DEFAULT_MODEL, OPENCODE_DEFAULT_PROVIDER

    if _model_config_loaded:
        return _model_config_data or {}

    # 尝试多种路径加载配置文件，优先使用工作目录下的 config/model_config.json
    paths_to_try = [
        os.path.join(OPENCODE_DEFAULT_DIRECTORY, "config", "model_config.json"),
        os.path.join("config", "model_config.json"),
        os.path.join(OPENCODE_DEFAULT_DIRECTORY, "..", "config", "model_config.json"),
    ]
    cfg = {}
    for p in paths_to_try:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"加载模型配置失败: {e}")
                cfg = {}
            break

    default_model = cfg.get("default_model") or OPENCODE_DEFAULT_MODEL
    default_provider = cfg.get("default_provider") or OPENCODE_DEFAULT_PROVIDER
    excluded = cfg.get("excluded_models") or []

    _model_config_data = {
        "default_model": default_model,
        "default_provider": default_provider,
        "excluded_models": excluded,
    }
    OPENCODE_DEFAULT_MODEL = default_model
    OPENCODE_DEFAULT_PROVIDER = default_provider
    _model_config_excluded = list(excluded)
    _model_config_loaded = True
    return _model_config_data


def reset_model_config_cache():
    """清除模型配置缓存，强制下次 load_model_config() 重新读取文件"""
    global _model_config_loaded, _model_config_data
    _model_config_loaded = False
    _model_config_data = None


def _is_model_excluded(provider_id: str, model_id: str) -> bool:
    """根据模型排除模式进行判断，模式支持 fnmatch 的通配匹配"""
    patterns = _model_config_excluded or []
    key = f"{provider_id}/{model_id}"
    for pat in patterns:
        if fnmatch.fnmatch(key, pat) or fnmatch.fnmatch(provider_id, pat) or fnmatch.fnmatch(model_id, pat):
            return True
    return False


@dataclass
class OpenCodeSession:
    """OpenCode会话信息"""
    session_id: str
    title: str
    created_at: float
    last_accessed: float
    directory: str = OPENCODE_DEFAULT_DIRECTORY


class OpenCodeClient:
    """OpenCode API客户端"""
    
    def __init__(self, base_url: str = OPENCODE_BASE_URL):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=300)  # 5分钟超时
        self.directory = OPENCODE_DEFAULT_DIRECTORY
        # 模型配置懒加载标记
        self._model_config_loaded = False
        
    def _get_headers(self, session_id: str = None) -> Dict[str, str]:
        """获取请求头"""
        directory_b64 = base64.b64encode(self.directory.encode()).decode()
        logger.info(f"[OpenCodeClient] x-opencode-directory: {self.directory} (b64: {directory_b64})")
        
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "x-opencode-directory": self.directory
        }
        
        if session_id:
            headers["Referer"] = f"{self.base_url}/{directory_b64}/session/{session_id}"
        else:
            headers["Referer"] = f"{self.base_url}/{directory_b64}/session"
            
        return headers
    
    async def create_session(
        self, 
        title: Optional[str] = None,
        directory: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        创建新会话
        
        Returns:
            (session_id, error_message)
        """
        if directory:
            self.directory = directory
            
        session_title = title or "语音交互会话"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.post(
                    f"{self.base_url}/session",
                    headers=self._get_headers(),
                    json={"title": session_title}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        session_id = data.get("id")
                        logger.info(f"创建OpenCode会话成功: {session_id}")
                        return session_id, None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"创建会话失败: {e}")
            return None, str(e)
    
    async def list_sessions(self, limit: int = 20) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        列出所有会话
        
        Returns:
            (sessions_list, error_message)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.get(
                    f"{self.base_url}/session",
                    params={"limit": limit}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict) and "sessions" in data:
                            return data["sessions"], None
                        elif isinstance(data, list):
                            return data, None
                        return [], None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"列出会话失败: {e}")
            return None, str(e)
    
    async def send_message(
        self,
        session_id: str,
        message: str,
        prefix_data: Optional[Dict[str, Any]] = None,
        skip_prefix: bool = False,
        agent: str = None,
        model_id: str = None,
        provider_id: str = None,
        directory: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        发送消息到OpenCode (使用prompt_async端点)
        
        Args:
            session_id: 会话ID
            message: 消息内容
            prefix_data: 前缀数据字典，包含speaker, location, prompt, message_type等
            skip_prefix: 为 True 时不添加 <Axeuh-home-system> 包装
            agent: 代理名称
            model_id: 模型ID
            provider_id: 提供商ID
            directory: 工作目录
        """
        if directory:
            self.directory = directory

        if skip_prefix:
            # 不加任何前缀包装，原始消息直接发送
            formatted_message = message
            logger.info(f"[OPENCODE-RAW] skip_prefix=True, message_preview={message[:80]}")
        else:
            now = datetime.now()
            # 统一注入当前时间（无论前缀来自何处）
            cur_datetime = now.strftime("%Y-%m-%d %H:%M:%S")

            # 默认前缀数据
            default_prefix = {
                "speaker": "用户",
                "prompt": "必须第一时间使用tts_speak工具中文回复语音消息。",
                "current_datetime": cur_datetime,
            }

            # 使用传入的前缀或默认值
            if prefix_data is None:
                prefix_data = default_prefix
            else:
                # 强制注入时间字段（覆盖所有自定义前缀路径）
                prefix_data["current_datetime"] = cur_datetime

            formatted_message = f"""<Axeuh-home-system>
{json.dumps(prefix_data, ensure_ascii=False, indent=2)}
</Axeuh-home-system>

{message}"""
        
        # 构建请求体
        body = {
            "agent": agent or OPENCODE_DEFAULT_AGENT,
            "model": {
                "modelID": model_id or OPENCODE_DEFAULT_MODEL,
                "providerID": provider_id or OPENCODE_DEFAULT_PROVIDER
            },
            "parts": [
                {
                    "type": "text",
                    "text": formatted_message
                }
            ]
        }
        
        logger.info(f"[OPENCODE-REQ] POST /session/{session_id}/prompt_async")
        logger.info(f"[OPENCODE-REQ] agent={agent or OPENCODE_DEFAULT_AGENT}")
        logger.info(f"[OPENCODE-REQ] model={model_id or OPENCODE_DEFAULT_MODEL}, provider={provider_id or OPENCODE_DEFAULT_PROVIDER}")
        logger.info(f"[OPENCODE-REQ] full_request_body=\n{json.dumps(body, ensure_ascii=False, indent=2)}")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.post(
                    f"{self.base_url}/session/{session_id}/prompt_async",
                    headers=self._get_headers(session_id),
                    json=body
                ) as response:
                    # HTTP 200或204都表示成功
                    if response.status in (200, 204):
                        logger.info(f"消息发送成功: session={session_id}, agent={agent or OPENCODE_DEFAULT_AGENT}, content={message[:30]}...")
                        return True, None
                    else:
                        text = await response.text()
                        logger.error(f"消息发送失败: HTTP {response.status}, {text}")
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False, str(e)
    
    async def send_raw_message(
        self,
        session_id: str,
        message: str,
        agent: str = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        发送原始消息到 OpenCode，不添加任何前缀包装（<Axeuh-home-system> 等）。
        """
        body = {
            "agent": agent or OPENCODE_DEFAULT_AGENT,
            "model": {
                "modelID": OPENCODE_DEFAULT_MODEL,
                "providerID": OPENCODE_DEFAULT_PROVIDER
            },
            "parts": [
                {"type": "text", "text": message}
            ]
        }
        logger.info(f"[RAWMSG-SENT] session={session_id} text_preview={message[:80]}")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.post(
                    f"{self.base_url}/session/{session_id}/prompt_async",
                    headers=self._get_headers(session_id),
                    json=body
                ) as response:
                    if response.status in (200, 204):
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            return False, str(e)

    async def abort_session(
        self, 
        session_id: str,
        directory: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        中止会话当前任务
        
        Returns:
            (success, error_message)
        """
        work_dir = directory or OPENCODE_DEFAULT_DIRECTORY
        directory_b64 = base64.b64encode(work_dir.encode()).decode()
        logger.info(f"[OpenCodeClient] abort x-opencode-directory: {work_dir} (b64: {directory_b64})")
        
        headers = {
            "Content-Type": "application/json",
            "Referer": f"{self.base_url}/{directory_b64}/session/{session_id}",
            "x-opencode-directory": work_dir
        }
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
                async with client.post(
                    f"{self.base_url}/session/{session_id}/abort",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"中止会话成功: {session_id}")
                        return True, None
                    else:
                        text = await response.text()
                        return False, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"中止会话失败: {e}")
            return False, str(e)
    
    async def get_session_status(self, session_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """获取会话状态"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.get(
                    f"{self.base_url}/session/{session_id}"
                ) as response:
                    if response.status == 200:
                        return await response.json(), None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            return None, str(e)

    async def get_all_sessions_status(self) -> Tuple[Optional[Dict], Optional[str]]:
        """获取所有会话的状态映射
        
        调用 GET /session/status 返回 {session_id: {state, lastActivity}}
        
        Returns:
            (status_map, error_message)
        """
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.get(
                    f"{self.base_url}/session/status"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data, None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"获取会话状态失败: {e}")
            return None, str(e)

    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
        before: Optional[str] = None
    ) -> Tuple[Optional[List[Dict]], Optional[str]]:
        """
        获取会话消息历史

        Args:
            session_id: 会话ID
            limit: 返回消息数量上限
            before: 分页游标，获取此消息之前的记录

        Returns:
            (messages_list, error_message)
        """
        try:
            params = {"limit": limit}
            if before:
                params["before"] = before

            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.get(
                    f"{self.base_url}/session/{session_id}/message",
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 兼容不同返回格式
                        if isinstance(data, dict):
                            msgs = data.get("messages") or data.get("data") or []
                        elif isinstance(data, list):
                            msgs = data
                        else:
                            msgs = []
                        return msgs, None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"获取会话消息失败: {e}")
            return None, str(e)

    async def get_providers(self) -> Tuple[Optional[Dict], Optional[str]]:
        """获取OpenCode提供商和模型列表

        调用 GET /config/providers 获取所有可用提供商及其模型列表

        Returns:
            (providers_data, error_message)
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
                async with client.get(
                    f"{self.base_url}/config/providers",
                    headers={"Accept": "application/json"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data, None
                    else:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
        except Exception as e:
            logger.error(f"获取提供商列表失败: {e}")
            return None, str(e)

    async def get_available_models(self) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """从 OpenCode /config/providers 获取可用模型清单，并应用排除策略"""
        # 确保模型配置已加载（懒加载行为）
        load_model_config()
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as client:
                async with client.get(f"{self.base_url}/config/providers", headers=self._get_headers()) as response:
                    if response.status != 200:
                        text = await response.text()
                        return None, f"HTTP {response.status}: {text}"
                    data = await response.json()
                    providers: List[Dict[str, Any]] = []
                    # 兼容多种返回结构
                    items = []
                    if isinstance(data, dict):
                        items = data.get("providers") or data.get("providers_list") or []
                    elif isinstance(data, list):
                        items = data
                    if not isinstance(items, list):
                        items = []

                    for prov in items:
                        if not isinstance(prov, dict):
                            continue
                        provider_id = (prov.get("provider_id") or prov.get("providerId") or prov.get("id") or prov.get("name"))
                        provider_name = (prov.get("provider_name") or prov.get("providerName") or prov.get("name"))
                        models_raw = prov.get("models") or {}
                        # 支持两种格式：列表格式[{"id":..., "name":...}] 或字典格式{"model_id": {"id":..., "name":...}}
                        if isinstance(models_raw, dict):
                            # 字典格式: {"deepseek-chat": {"id": "deepseek-chat", "name": "DeepSeek Chat", ...}}
                            models_iter = models_raw.items()
                        elif isinstance(models_raw, list):
                            # 列表格式: [{"id":..., "name":...}, ...]
                            models_iter = [(m.get("id"), m) for m in models_raw if isinstance(m, dict)]
                        else:
                            models_iter = []
                        
                        for model_id, m in models_iter:
                            if not isinstance(m, dict):
                                continue
                            # 从模型对象中提取信息
                            model_id = (m.get("model_id") or m.get("modelId") or m.get("id") or model_id)
                            model_name = (m.get("model_name") or m.get("modelName") or m.get("name"))
                            if not provider_id or not model_id:
                                continue
                            if _is_model_excluded(provider_id, model_id):
                                continue
                            providers.append({
                                "provider_id": provider_id,
                                "provider_name": provider_name or provider_id,
                                "model_id": model_id,
                                "model_name": model_name or model_id,
                            })
                    return providers, None
        except Exception as e:
            return None, str(e)


# 单例实例
_opencode_client: Optional[OpenCodeClient] = None


def get_opencode_client() -> OpenCodeClient:
    """获取OpenCode客户端单例（自动探测可用端口）"""
    global _opencode_client
    if _opencode_client is None:
        discovered = discover_opencode_url()
        _opencode_client = OpenCodeClient(base_url=discovered)
    return _opencode_client
