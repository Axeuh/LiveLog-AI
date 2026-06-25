"""
SSE转发器 - 将主智能体的SSE事件转发到监督智能体会话

实现机制：
1. 监听主智能体的SSE事件流
2. 累积流式消息内容（message.part.delta）
3. 转发完整消息（message.updated）
4. 格式化工具调用事件（message.part.updated）
"""

import aiohttp
import asyncio
import json
import logging
import base64
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import json
import logging
import base64
from typing import Dict, Any, Optional

from services.sse_listener import get_sse_listener

logger = logging.getLogger(__name__)


class SSEForwarder:
    """
    SSE转发器
    
    将主智能体的SSE事件转发到监督智能体会话
    """
    
    # 过滤的事件类型（不转发）
    FILTERED_EVENTS = {
        'server.connected',       # 连接状态
        'server.heartbeat',       # 心跳
        'session.status',         # 会话状态
        'session.diff',           # 会话差异
        'session.created',        # 会话创建
        'session.updated',        # 会话更新
        'todo.updated',           # Todo更新
        'lsp.client.diagnostics', # LSP诊断
        'tui.toast.show',         # TUI通知
        'file.edited',            # 文件编辑
        'file.watcher.updated',   # 文件监视更新
    }
    
    def __init__(self, opencode_url: str = None):
        """
        初始化SSE转发器
        
        Args:
            opencode_url: OpenCode服务地址
        """
        if opencode_url is None:
            from config.config import get_config
            opencode_url = get_config().OPENCODE_URL
        self.opencode_url = opencode_url
        self.supervisor_session_id: Optional[str] = None
        self.main_task_session_id: Optional[str] = None
        self._is_running = False
        self._monitored_sessions: Dict[str, str] = {}  # session_id -> source_name
        
        # 消息累积缓冲区
        self._message_buffers: Dict[str, str] = {}  # messageID -> accumulated_text
        self._session_messages: Dict[str, str] = {}  # sessionID -> messageID (当前消息)
        self._buffer_lock = asyncio.Lock()
        
        # 已转发消息ID集合（用于去重）
        self._forwarded_message_ids: set = set()
        self._forwarded_lock = asyncio.Lock()  # 去重集合的锁
        
    async def set_supervisor_session(self, session_id: str):
        """设置监督智能体会话ID"""
        self.supervisor_session_id = session_id
        logger.info(f"设置监督智能体会话: {session_id}")
        
    async def set_main_task_session(self, session_id: str):
        """设置主任务智能体会话ID"""
        self.main_task_session_id = session_id
        logger.info(f"设置主任务智能体会话: {session_id}")
        
    async def add_monitored_session(self, session_id: str, source_name: str):
        """
        添加监控的会话
        
        Args:
            session_id: 会话ID
            source_name: 来源名称（如 "main-task", "explore", "librarian" 等）
        
        注意：监督智能体不应该被添加到监控列表，它是接收方
        """
        # 检查是否是监督智能体
        if session_id == self.supervisor_session_id:
            print(f"[SSEForwarder] 警告：尝试添加监督智能体到监控列表，已拒绝: {session_id[:16]}...")
            logger.warning(f"尝试添加监督智能体到监控列表，已拒绝: {session_id}")
            return
        
        # 检查是否是监督智能体类型
        if source_name == "supervisor":
            print(f"[SSEForwarder] 警告：尝试添加监督智能体类型到监控列表，已拒绝: {source_name}")
            logger.warning(f"尝试添加监督智能体类型到监控列表，已拒绝: {source_name}")
            return
        
        self._monitored_sessions[session_id] = source_name
        print(f"[SSEForwarder] 添加会话监控: {session_id[:16]}... -> {source_name}")
        logger.info(f"添加会话监控: {session_id} -> {source_name}")
        
        # 同时通知 SSEListener 开始监听这个会话
        sse_listener = get_sse_listener()
        await sse_listener.start_listening(session_id)
    def remove_monitored_session(self, session_id: str):
        """
        移除监控的会话
        
        Args:
            session_id: 会话ID
        """
        if session_id in self._monitored_sessions:
            del self._monitored_sessions[session_id]
            logger.info(f"移除会话监控: {session_id}")
        
    async def start(self):
        """启动SSE转发"""
        if self._is_running:
            return
            
        self._is_running = True
        
        # 注册SSE事件回调
        sse_listener = get_sse_listener()
        sse_listener.add_callback(self._on_sse_event)
        
        logger.info("SSE转发器启动")
        
    async def stop(self):
        """停止SSE转发"""
        self._is_running = False
        
        # 移除回调
        sse_listener = get_sse_listener()
        sse_listener.remove_callback(self._on_sse_event)
        
        # 清理缓冲区
        async with self._buffer_lock:
            self._message_buffers.clear()
            self._session_messages.clear()
        
        # 清理监控列表
        self._monitored_sessions.clear()
        
        # 清理去重集合
        async with self._forwarded_lock:
            self._forwarded_message_ids.clear()
        
        logger.info("SSE转发器停止")
        
    async def _on_sse_event(self, session_id: str, event: Dict[str, Any]):
        """
        SSE事件回调
        
        Args:
            session_id: 来源会话ID
            event: 事件数据
        """
        print(f"[SSEForwarder] 收到事件: session={session_id[:16]}..., monitored={list(self._monitored_sessions.keys())}")
        
        # 跳过监督智能体自己的事件
        if session_id == self.supervisor_session_id:
            return
        
        # 检查是否在监控列表中
        if session_id not in self._monitored_sessions:
            print(f"[SSEForwarder] 会话不在监控列表中!")
            return
        
        # 解析事件类型
        payload = event.get('payload', {})
        event_type = payload.get('type', 'unknown')
        print(f"[SSEForwarder] 处理事件: type={event_type}")
        
        # 过滤不需要的事件
        if event_type in self.FILTERED_EVENTS:
            return
        
        # 获取来源标记
        source = self._monitored_sessions.get(session_id, "unknown")
        
        # 根据事件类型处理
        if event_type == 'message.part.delta':
            # 累积流式内容，不转发
            await self._handle_delta(payload, session_id)
            return
        
        elif event_type == 'message.updated':
            # 消息更新，转发完整内容
            await self._handle_message_updated(payload, source, session_id)
            return
        
        elif event_type == 'message.part.updated':
            # 检查是否是工具调用事件
            props = payload.get('properties', {})
            part = props.get('part', {})
            part_type = part.get('type', '')
            
            # 只处理工具调用，text/step-finish 由 message.updated 处理
            if part_type == 'tool':
                await self._handle_tool_event(payload, source, session_id)
            # text 和 step-finish 不再这里处理，避免重复转发
            return
    async def _handle_delta(self, payload: Dict[str, Any], session_id: str):
        """
        处理流式增量事件（累积内容，不转发）
        
        Args:
            payload: 事件载荷
            session_id: 会话ID
        """
        props = payload.get('properties', {})
        message_id = props.get('messageID', '')
        delta = props.get('delta', '')
        
        if not message_id or not delta:
            return
        
        async with self._buffer_lock:
            # 累积内容
            if message_id not in self._message_buffers:
                self._message_buffers[message_id] = ''
            self._message_buffers[message_id] += delta
            
            # 记录当前会话的消息ID
            self._session_messages[session_id] = message_id
        
    async def _handle_message_updated(self, payload: Dict[str, Any], source: str, session_id: str):
        """
        处理消息更新事件
        
        Args:
            payload: 事件载荷
            source: 来源标记
            session_id: 会话ID
        """
        props = payload.get('properties', {})
        info = props.get('info', {})
        role = info.get('role', 'unknown')
        message_id = info.get('id', '')
        
        # 调试日志：打印关键信息
        supervisor_short = self.supervisor_session_id[:16] if self.supervisor_session_id else 'None'
        message_short = message_id[:16] if message_id else 'None'
        print(f"[SSEForwarder] message.updated: role={role}, message_id={message_short}..., supervisor={supervisor_short}...")
        # 构建转发文本 - 简洁格式
        
        if role == 'assistant':
            # AI回复：从缓冲区获取累积内容
            
            # 去重检查：避免重复转发同一条消息（在锁保护下）
            async with self._forwarded_lock:
                if message_id in self._forwarded_message_ids:
                    print(f"[SSEForwarder] assistant分支: 消息已转发过，跳过: {message_short}...")
                    return
                # 立即标记为已转发，防止并发重复
                self._forwarded_message_ids.add(message_id)
            
            async with self._buffer_lock:
                content = self._message_buffers.get(message_id, '')
                print(f"[SSEForwarder] assistant分支: 缓冲区内容长度={len(content)}, message_id={message_short}...")
                # 清理缓冲区
                if message_id in self._message_buffers:
                    del self._message_buffers[message_id]
                if session_id in self._session_messages:
                    del self._session_messages[session_id]
            
            # 如果缓冲区为空，尝试通过API获取内容
            if not content:
                print(f"[SSEForwarder] assistant分支: 缓冲区为空，尝试API获取最近消息")
                content = await self._fetch_latest_assistant_content(session_id, message_id)
                print(f"[SSEForwarder] assistant分支: API返回内容长度={len(content) if content else 0}")
            
            if content:
                event_text = f"[AI] {content}"
                print(f"[SSEForwarder] 准备转发AI回复: 内容长度={len(content)}")
                await self._forward_to_supervisor(event_text)
            else:
                print(f"[SSEForwarder] assistant分支: 内容为空，不转发")

        elif role == 'user':
            # 用户消息：调用API获取内容
            
            # 去重检查（在锁保护下）
            async with self._forwarded_lock:
                if message_id in self._forwarded_message_ids:
                    print(f"[SSEForwarder] user分支: 消息已转发过，跳过: {message_short}...")
                    return
                # 立即标记为已转发
                self._forwarded_message_ids.add(message_id)
            
            # 获取用户消息内容并转发
            content = await self._fetch_user_message_content(session_id, message_id)
            if content:
                event_text = f"[用户] {content}"
                print(f"[SSEForwarder] 准备转发用户消息: 内容长度={len(content)}")
                await self._forward_to_supervisor(event_text)
            else:
                print(f"[SSEForwarder] user分支: 内容为空，不转发")

        else:
            print(f"[SSEForwarder] role不是assistant或user: role={role}")
    async def _fetch_user_message_content(self, session_id: str, message_id: str) -> str:
        """
        通过API获取用户消息内容
        
        Args:
            session_id: 会话ID
            message_id: 消息ID
            
        Returns:
            消息内容
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                # 获取会话消息列表
                async with client.get(
                    f"{self.opencode_url}/session/{session_id}/message"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # API 直接返回消息列表
                        messages = data
                        for msg in messages:
                            info = msg.get('info', {})
                            if info.get('id') == message_id:
                                # 提取消息内容
                                parts = msg.get('parts', [])
                                for part in parts:
                                    if part.get('type') == 'text':
                                        return part.get('text', '')
                        return ''
                    else:
                        logger.warning(f"获取会话消息失败: HTTP {response.status}")
                        return ''
        except Exception as e:
            logger.error(f"获取用户消息内容失败: {e}")
            return ''

    async def _fetch_assistant_message_content(self, session_id: str, message_id: str) -> str:
        """
        通过API获取assistant消息的text part内容
        
        Args:
            session_id: 会话ID
            message_id: 消息ID
            
        Returns:
            消息内容
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                # 获取会话消息列表
                async with client.get(
                    f"{self.opencode_url}/session/{session_id}/message"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # API 直接返回消息列表
                        messages = data
                        for msg in messages:
                            info = msg.get('info', {})
                            if info.get('id') == message_id:
                                # 提取消息内容
                                parts = msg.get('parts', [])
                                for part in parts:
                                    if part.get('type') == 'text':
                                        return part.get('text', '')
                        return ''
                    else:
                        logger.warning(f"获取assistant消息失败: HTTP {response.status}")
                        return ''
        except Exception as e:
            logger.error(f"获取assistant消息内容失败: {e}")
            return ''
    

    async def _fetch_latest_assistant_content(self, session_id: str, current_message_id: str = '') -> str:
        """
        获取会话中指定的assistant消息内容
        
        Args:
            session_id: 会话ID
            current_message_id: 当前消息的ID（可选，用于验证）
            
        Returns:
            指定assistant消息的内容
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                # 获取会话消息列表
                async with client.get(
                    f"{self.opencode_url}/session/{session_id}/message"
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = data
                        
                        # 只获取最新的一条assistant消息
                        for msg in reversed(messages):
                            info = msg.get('info', {})
                            if info.get('role') == 'assistant':
                                # 如果提供了message_id，检查是否匹配
                                msg_id = info.get('id', '')
                                if current_message_id and msg_id != current_message_id:
                                    print(f"[SSEForwarder] 跳过非目标消息: {msg_id[:16]}... != {current_message_id[:16]}...")
                                    continue
                                
                                # 提取这条消息的内容
                                parts = msg.get('parts', [])
                                content_parts = []
                                tool_calls = []
                                
                                for part in parts:
                                    part_type = part.get('type', '')
                                    if part_type == 'text':
                                        text = part.get('text', '')
                                        if text:
                                            content_parts.append(text)
                                    elif part_type == 'tool':
                                        tool = part.get('tool', 'unknown')
                                        state = part.get('state', {})
                                        status = state.get('status', '') if isinstance(state, dict) else ''
                                        if status == 'completed':
                                            tool_calls.append(f"[工具] {tool}")
                                
                                # 组合内容
                                result = ''
                                if content_parts:
                                    result += '\n'.join(content_parts)
                                if tool_calls:
                                    if result:
                                        result += '\n\n'
                                    result += '工具调用:\n' + '\n'.join(tool_calls)
                                
                                print(f"[SSEForwarder] _fetch_latest: 找到目标消息 {msg_id[:16]}..., content_parts={len(content_parts)}, tool_calls={len(tool_calls)}")
                                return result
                        
                        return ''
                    else:
                        logger.warning(f"获取assistant消息失败: HTTP {response.status}")
                        return ''
        except Exception as e:
            logger.error(f"获取最新assistant内容失败: {e}")
            return ''
    async def _handle_tool_event(self, payload: Dict[str, Any], source: str, session_id: str):
        """
        处理工具调用事件
        
        Args:
            payload: 事件载荷
            source: 来源标记
            session_id: 会话ID
        """
        props = payload.get('properties', {})
        part = props.get('part', {})
        part_type = part.get('type', '')
        
        # 只处理工具类型
        if part_type != 'tool':
            return
        
        tool = part.get('tool', 'unknown')
        state = part.get('state', {})
        status = state.get('status', '') if isinstance(state, dict) else ''
        
        # 只转发 completed（完成）状态，不转发 pending（开始）
        if status != 'completed':
            return
        if status not in ('pending', 'completed'):
            return
        
        # 构建转发文本 - 简洁格式
        
        if status == 'pending':
            # 工具开始执行
            tool_input = state.get('input', {}) if isinstance(state, dict) else {}
            input_formatted = self._format_tool_input(tool, tool_input)
            event_text = f"[工具] 开始: {tool}\n输入: {input_formatted}"
            await self._forward_to_supervisor(event_text)
            
        elif status == 'completed':
            # 工具执行完成
            tool_output = state.get('output', '') if isinstance(state, dict) else ''
            output_formatted = self._format_tool_output(tool, tool_output)
            event_text = f"[工具] 完成: {tool}\n输出: {output_formatted}"
            await self._forward_to_supervisor(event_text)
    
    def _format_tool_input(self, tool: str, input_data: Dict[str, Any]) -> str:
        """
        格式化工具输入
        
        Args:
            tool: 工具名称
            input_data: 输入数据
            
        Returns:
            格式化后的字符串
        """
        if tool in ('read', 'write', 'edit'):
            # 文件路径
            return input_data.get('filePath', '')
        
        elif tool == 'bash':
            # 完整命令
            return input_data.get('command', '')
        
        elif tool == 'task':
            # 子智能体类型 + 任务描述
            subagent = input_data.get('subagent_type', input_data.get('category', 'unknown'))
            desc = input_data.get('description', input_data.get('prompt', ''))[:50]
            return f"{subagent} - {desc}"
        
        elif tool == 'skill_mcp':
            # 技能名 + 参数
            mcp_name = input_data.get('mcp_name', '')
            tool_name = input_data.get('tool_name', '')
            return f"{mcp_name}/{tool_name}"
        
        else:
            # 其他工具：JSON前100字符
            try:
                json_str = json.dumps(input_data, ensure_ascii=False)
                return json_str[:100]
            except Exception:
                return str(input_data)[:100]
    
    def _format_tool_output(self, tool: str, output: Any) -> str:
        """
        格式化工具输出
        
        Args:
            tool: 工具名称
            output: 输出数据
            
        Returns:
            格式化后的字符串
        """
        if tool == 'read':
            # 显示行数
            output_str = str(output) if output else ''
            lines = output_str.count('\n') + 1 if output_str else 0
            return f"读取了 {lines} 行"
        
        elif tool == 'write':
            return "文件已写入"
        
        elif tool == 'edit':
            return "文件已编辑"
        
        elif tool == 'bash':
            # 输出前200字符
            output_str = str(output)[:200] if output else ''
            return output_str.replace('\n', ' ')
        
        elif tool in ('glob', 'grep'):
            # 结果数量
            output_str = str(output) if output else ''
            count = output_str.count('\n') + 1 if output_str else 0
            return f"找到 {count} 个结果"
        
        elif tool == 'task':
            return "子任务完成"
        
        else:
            # 其他工具：输出前100字符
            output_str = str(output)[:100] if output else ''
            return output_str.replace('\n', ' ')
    
    async def _forward_to_supervisor(self, event_text: str):
        """
        转发文本到监督智能体会话
        
        Args:
            event_text: 要转发的文本
        """
        print(f"[SSEForwarder] _forward_to_supervisor: supervisor_session_id={self.supervisor_session_id[:16] if self.supervisor_session_id else 'None'}...")
        print(f"[SSEForwarder] _forward_to_supervisor: event_text前50字符={event_text[:50]}...")
        if not self.supervisor_session_id:
            print(f"[SSEForwarder] 监督智能体会话未设置，无法转发")
            logger.warning("监督智能体会话未设置，无法转发")
            return
        
        try:
            # 构建消息内容，添加XML包装和时间戳
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            xml_header = '<Axeuh-home-system>\n{\n  "source": "main-task",\n  "type": "forwarded_message",\n  "timestamp": "' + timestamp + '"\n}\n</Axeuh-home-system>\n\n'
            formatted_message = xml_header + event_text
            
            body = {
                "agent": "supervisor",
                "model": {
                    "modelID": "glm-5",
                    "providerID": "alibaba-coding-plan-cn"
                },
                "parts": [
                    {
                        "type": "text",
                        "text": formatted_message
                    }
                ]
            }
            
            # 构建 headers
            from config.config import get_config
            directory = get_config().OPENCODE_DIRECTORY
            directory_b64 = base64.b64encode(directory.encode()).decode()
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Origin": self.opencode_url,
                "x-opencode-directory": directory,
                "Referer": f"{self.opencode_url}/{directory_b64}/session/{self.supervisor_session_id}"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                async with client.post(
                    f"{self.opencode_url}/session/{self.supervisor_session_id}/prompt_async",
                    headers=headers,
                    json=body
                ) as response:
                    print(f"[SSEForwarder] OpenCode 响应状态: {response.status}")
                    if response.status in (200, 204):
                        response_text = await response.text()
                        print(f"[SSEForwarder] OpenCode 响应内容: {response_text[:100]}...")
                        logger.info(f"转发成功: {event_text[:50]}...")
                    else:
                        response_text = await response.text()
                        print(f"[SSEForwarder] OpenCode 错误响应: {response.status}, {response_text[:100]}...")
                        logger.warning(f"转发失败: HTTP {response.status}")
                    if response.status in (200, 204):
                        logger.info(f"转发成功: {event_text[:50]}...")
                    else:
                        logger.warning(f"转发失败: HTTP {response.status}")
                        
        except Exception as e:
            logger.error(f"转发SSE事件失败: {e}")
            
    async def create_supervisor_session(self) -> Optional[str]:
        """
        创建监督智能体会话
        
        Returns:
            会话ID或None
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as client:
                async with client.post(
                    f"{self.opencode_url}/session",
                    json={"title": "监督智能体会话"}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        session_id = data.get("id")
                        self.supervisor_session_id = session_id
                        logger.info(f"创建监督智能体会话成功: {session_id}")
                        return session_id
                    else:
                        logger.error(f"创建监督智能体会话失败: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"创建监督智能体会话失败: {e}")
            return None


# 全局单例
_sse_forwarder_instance: Optional[SSEForwarder] = None


def get_sse_forwarder() -> SSEForwarder:
    """获取SSE转发器单例"""
    global _sse_forwarder_instance
    if _sse_forwarder_instance is None:
        _sse_forwarder_instance = SSEForwarder()
    return _sse_forwarder_instance


def set_sse_forwarder(forwarder: SSEForwarder):
    """设置SSE转发器单例"""
    global _sse_forwarder_instance
    _sse_forwarder_instance = forwarder