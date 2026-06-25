"""
OpenCode Gateway - 统一的 OpenCode 通信入口

功能：
1. 所有 OpenCode 调用经过此 Gateway
2. 支持 offline 模拟模式（无需 OpenCode 服务）
3. 统一错误格式：{"ok": bool, "data": ..., "error": {"source": "opencode|system|mock", "detail": str}}
4. 统一的默认模型/提供商配置
"""

import logging
from typing import Optional, Dict, Any, List
from config.config import get_config
from services.opencode_client import (
    get_opencode_client, OpenCodeClient,
    OPENCODE_DEFAULT_AGENT
)

logger = logging.getLogger(__name__)


class OpenCodeGateway:
    """OpenCode 统一网关"""

    def __init__(self):
        cfg = get_config()
        self._offline_mode = cfg.OPENCODE_MOCK_ENABLED
        self._client: Optional[OpenCodeClient] = None if self._offline_mode else get_opencode_client()
        self._default_model = cfg.OPENCODE_DEFAULT_MODEL
        self._default_provider = cfg.OPENCODE_DEFAULT_PROVIDER

    # ---- 统一返回格式 ----

    @staticmethod
    def _ok(data: Any = None) -> Dict:
        """构造成功响应"""
        return {"ok": True, "data": data, "error": None}

    @staticmethod
    def _fail(source: str, detail: str, code: int = 500) -> Dict:
        """构造错误响应"""
        return {"ok": False, "data": None, "error": {"source": source, "detail": detail, "code": code}}

    # ---- 配置 ----

    def get_default_model(self) -> str:
        return self._default_model

    def get_default_provider(self) -> str:
        return self._default_provider

    # ---- 模拟数据 ----

    def _mock_session_id(self) -> str:
        import uuid
        return f"mock_ses_{uuid.uuid4().hex[:12]}"

    def _mock_sessions(self) -> List[Dict]:
        return [
            {"session_id": self._mock_session_id(), "title": "模拟会话1", "created_at": 0, "last_accessed": 0},
            {"session_id": self._mock_session_id(), "title": "模拟会话2", "created_at": 0, "last_accessed": 0},
        ]

    # ---- 健康检查 ----

    async def health_check(self) -> Dict:
        """检查 OpenCode 服务状态"""
        if self._offline_mode:
            return self._ok({"status": "mock", "mode": "offline"})
        try:
            from services.opencode_client import get_opencode_client
            client = get_opencode_client()
            result, error = await client.list_sessions(limit=1)
            if error:
                return self._ok({"status": "offline", "mode": "online", "detail": error})
            return self._ok({"status": "online", "mode": "online"})
        except Exception as e:
            return self._ok({"status": "offline", "mode": "online", "detail": str(e)})

    # ---- 会话管理 ----

    async def create_session(self, title: Optional[str] = None,
                             directory: Optional[str] = None) -> Dict:
        """创建 OpenCode 会话"""
        if self._offline_mode:
            return self._ok({"session_id": self._mock_session_id(), "title": title or "模拟会话"})
        try:
            session_id, error = await self._client.create_session(title=title, directory=directory)
            if error:
                return self._fail("opencode", error)
            return self._ok({"session_id": session_id, "title": title or "语音交互会话"})
        except Exception as e:
            return self._fail("system", f"create_session 异常: {e}")

    async def list_sessions(self, limit: int = 20) -> Dict:
        """列出 OpenCode 会话"""
        if self._offline_mode:
            return self._ok({"sessions": self._mock_sessions()})
        try:
            sessions, error = await self._client.list_sessions(limit=limit)
            if error:
                return self._fail("opencode", error)
            # 统一 session_id 字段
            normalized = []
            for s in (sessions or []):
                if isinstance(s, dict) and "id" in s and "session_id" not in s:
                    s["session_id"] = s["id"]
                normalized.append(s)
            return self._ok({"sessions": normalized})
        except Exception as e:
            return self._fail("system", f"list_sessions 异常: {e}")

    async def get_session_status(self, session_id: str) -> Dict:
        """获取会话状态"""
        if self._offline_mode:
            return self._ok({"session_id": session_id, "status": "active"})
        try:
            data, error = await self._client.get_session_status(session_id)
            if error:
                return self._fail("opencode", error)
            return self._ok(data or {})
        except Exception as e:
            return self._fail("system", f"get_session_status 异常: {e}")

    async def abort_session(self, session_id: str,
                            directory: Optional[str] = None) -> Dict:
        """中止会话任务"""
        if self._offline_mode:
            return self._ok({"aborted": True, "session_id": session_id})
        try:
            success, error = await self._client.abort_session(session_id, directory=directory)
            if error:
                return self._fail("opencode", error)
            return self._ok({"aborted": success, "session_id": session_id})
        except Exception as e:
            return self._fail("system", f"abort_session 异常: {e}")

    # ---- 消息发送 ----

    async def send_message(self, session_id: str, message: str,
                           prefix_data: Optional[Dict] = None,
                           agent: Optional[str] = None,
                           model_id: Optional[str] = None,
                           provider_id: Optional[str] = None,
                           directory: Optional[str] = None) -> Dict:
        """发送消息到 OpenCode"""
        if self._offline_mode:
            return self._ok({"sent": True, "session_id": session_id,
                             "message": message[:50] + "..." if len(message) > 50 else message})
        try:
            m_id = model_id or self._default_model
            p_id = provider_id or self._default_provider
            agent_name = agent or OPENCODE_DEFAULT_AGENT
            logger.info(f"[GATEWAY] agent={agent_name}, model={m_id}, provider={p_id}, "
                        f"session={session_id}, message_preview={message[:60]}")
            success, error = await self._client.send_message(
                session_id=session_id, message=message,
                prefix_data=prefix_data, agent=agent_name,
                model_id=m_id, provider_id=p_id, directory=directory
            )
            if error:
                return self._fail("opencode", error)
            return self._ok({"sent": success, "session_id": session_id})
        except Exception as e:
            return self._fail("system", f"send_message 异常: {e}")

    # ---- 统一语音消息发送 ----

    async def send_voice_to_opencode(self, text: str, agent: str = "main-task",
                                       prefix_data: Optional[Dict] = None) -> bool:
        """
        统一语音消息发送：获取/创建 agent 会话 → abort → send

        所有语音路径（STT路由/WebSocket音频/继续聊天）都调用此方法，
        确保与文字消息路径共享同一 agent 会话。
        """
        from services.stt_session_manager import get_session_manager

        session_mgr = get_session_manager()

        # 1. 优先使用 agent 绑定的会话（与文字消息路径一致）
        session_id = session_mgr.get_agent_session(agent)
        logger.info(f"[Gateway] send_voice_to_opencode agent={agent}, found_session={session_id}")

        # 2. 无会话 → 创建新会话并绑定到 agent
        if not session_id:
            result = await self.create_session(title="语音交互会话")
            if result["ok"]:
                session_id = result["data"]["session_id"]
                session_mgr.set_agent_session(agent, session_id)
                session_mgr.set_current_session(session_id, "语音交互会话")
                logger.info(f"[Gateway] 为 agent={agent} 创建会话: {session_id}")
            else:
                logger.error(f"[Gateway] 创建会话失败: {result.get('error', {}).get('detail', '未知错误')}")
                return False

        # 3. 中止当前 AI 任务
        await self.abort_session(session_id)

        # 4. 发送消息
        send_result = await self.send_message(
            session_id=session_id,
            message=text,
            prefix_data=prefix_data,
            agent=agent
        )

        if send_result["ok"]:
            logger.info(f"[Gateway] 语音消息已发送到 agent={agent}: {text[:50]}...")
            return True
        else:
            logger.error(f"[Gateway] 发送语音消息失败: {send_result.get('error', {})}")
            return False

    # ---- 活跃会话 ----

    async def get_active_sessions(self) -> Dict:
        """获取活跃会话列表（聚合 OpenCode + 本地）"""
        if self._offline_mode:
            return self._ok({"active_sessions": [
                {"session_id": self._mock_session_id(), "title": "活跃会话1", "agent": "voice-interaction"},
                {"session_id": self._mock_session_id(), "title": "活跃会话2", "agent": "main-task"},
            ]})
        try:
            result = await self.list_sessions(limit=50)
            if not result.get("ok"):
                return result
            sessions = result.get("data", {}).get("sessions", [])
            # OpenCode 返回的会话用 id 字段，前端期望 session_id
            normalized = []
            for s in sessions or []:
                if isinstance(s, dict):
                    if "id" in s and "session_id" not in s:
                        s["session_id"] = s["id"]
                    normalized.append(s)
            return self._ok({"active_sessions": normalized})
        except Exception as e:
            return self._fail("system", f"get_active_sessions 异常: {e}")

    # ---- 模型配置 ----

    async def get_available_models(self) -> Dict:
        """获取可用模型列表（从 OpenCode 实时获取）"""
        if self._offline_mode:
            return self._ok({"providers": [
                {"id": "mock-provider", "name": "模拟提供商", "models": [
                    {"id": self._default_model, "name": self._default_model}
                ]}
            ]})
        try:
            if not self._client:
                raise RuntimeError("OpenCode client not available")

            data, error = await self._client.get_providers()
            if error:
                logger.warning(f"从 OpenCode 获取模型列表失败: {error}，使用空列表")
                return self._ok({"providers": []})

            providers_raw = (data or {}).get("providers", [])
            providers_out = []

            for pv in providers_raw:
                if not isinstance(pv, dict):
                    continue
                pid = pv.get("id") or ""
                pname = pv.get("name") or pid
                models_raw = pv.get("models") or {}
                model_list = []

                if isinstance(models_raw, dict):
                    # models 是 {modelId: modelObj} 格式
                    for mid, mobj in models_raw.items():
                        if isinstance(mobj, dict):
                            model_list.append({
                                "id": mobj.get("id") or mid,
                                "name": mobj.get("name") or mobj.get("id") or mid
                            })
                elif isinstance(models_raw, list):
                    # models 是 [{id, name}] 格式
                    for mobj in models_raw:
                        if isinstance(mobj, dict) and mobj.get("id"):
                            model_list.append({
                                "id": mobj["id"],
                                "name": mobj.get("name") or mobj["id"]
                            })

                if pid and model_list:
                    providers_out.append({
                        "id": pid,
                        "name": pname,
                        "models": model_list
                    })

            return self._ok({"providers": providers_out})

        except Exception as e:
            logger.error(f"get_available_models 异常: {e}")
            return self._fail("system", f"get_available_models 异常: {e}")

    # ---- 会话消息 ----

    async def get_session_messages(self, session_id: str, limit: int = 100) -> Dict:
        """获取会话消息历史"""
        if self._offline_mode:
            return self._ok({"messages": [], "session_id": session_id})
        try:
            messages, error = await self._client.get_session_messages(session_id, limit=limit)
            if error:
                return self._fail("opencode", error)
            return self._ok({"messages": messages or [], "session_id": session_id})
        except Exception as e:
            return self._fail("system", f"get_session_messages 异常: {e}")

    # ---- 活跃会话 ----

    async def get_active_sessions(self) -> Dict:
        """获取活跃会话列表"""
        if self._offline_mode:
            return self._ok({"active_sessions": self._mock_sessions()})
        try:
            sessions, error = await self._client.list_sessions(limit=50)
            if error:
                return self._fail("opencode", error)
            return self._ok({"active_sessions": sessions or []})
        except Exception as e:
            return self._fail("system", f"get_active_sessions 异常: {e}")


# 单例
_gateway_instance: Optional[OpenCodeGateway] = None


def get_opencode_gateway() -> OpenCodeGateway:
    """获取 Gateway 单例"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = OpenCodeGateway()
    return _gateway_instance


def _reset_gateway():
    """重置 Gateway 单例（仅测试用）"""
    global _gateway_instance
    _gateway_instance = None
