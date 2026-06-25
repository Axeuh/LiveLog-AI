"""
组件管理器 - 核心服务
管理所有组件的生命周期
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import uuid
import subprocess
import asyncio.subprocess

from models import (
    Component, ComponentType, ComponentStatus,
    Terminal, BashComponent, StockComponent, TextComponent, CustomComponent,
    StockMode, ContentType
)

# ============ WebSocket 消息类型常量 ============
WS_MSG_CONNECTED = "connected"
WS_MSG_INITIAL_STATE = "initial_state"
WS_MSG_COMPONENT_CREATED = "component_created"
WS_MSG_COMPONENT_UPDATED = "component_updated"
WS_MSG_COMPONENT_DELETED = "component_deleted"


class ComponentManager:
    """组件管理器"""
    
    def __init__(self):
        self._components: Dict[str, Component] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        # WebSocket 客户端 - 按 user_id 分组
        self._ws_clients: Dict[str, List] = {}  # user_id -> [websocket, ...]
        self._ws_clients_anon: List = []  # 无 user_id 的客户端（本地访问）
    
    # ============ 组件基础操作 ============
    
    def _generate_id(self, prefix: str = "comp") -> str:
        """生成唯一 ID"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    def get_all(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有组件，可按 user_id 过滤

        Args:
            user_id: 过滤 user_id，None 返回所有组件（全局可见兼容）
        """
        if user_id:
            return [self._to_dict(c) for c in self._components.values()
                    if c.user_id == user_id or c.user_id is None]
        return [self._to_dict(c) for c in self._components.values()]
    
    def store(self, component: Component, broadcast: bool = True) -> Component:
        """存储组件到管理器
        
        Args:
            component: 要存储的组件实例
            broadcast: 是否广播创建事件（默认True）
        
        用于需要预设ID的场景（如 terminals.py 中终端组件
        需要与会话ID保持一致）。
        """
        self._components[component.id] = component
        if broadcast:
            self._broadcast_create(component)
        return component
    
    def get(self, component_id: str) -> Optional[Component]:
        """获取单个组件"""
        return self._components.get(component_id)
    
    def get_by_type(self, component_type: ComponentType) -> List[Component]:
        """按类型获取组件"""
        return [c for c in self._components.values() if c.type == component_type]
    
    def update(self, component_id: str, **kwargs) -> Optional[Component]:
        """更新组件属性"""
        comp = self._components.get(component_id)
        if not comp:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(comp, key):
                setattr(comp, key, value)
        
        comp.updated_at = datetime.now()
        self._broadcast_update(comp)
        return comp
    
    def delete(self, component_id: str) -> Dict[str, Any]:
        """删除组件（自动清理）"""
        comp = self._components.get(component_id)
        if not comp:
            return {"success": False, "error": "Component not found"}
        
        cleanup_actions = []
        comp_type = comp.type
        comp_user_id = comp.user_id  # 保存 user_id 用于广播
        
        # 根据类型执行清理
        if comp_type == ComponentType.TERMINAL:
            cleanup_actions = self._cleanup_terminal(component_id)
        elif comp_type == ComponentType.BASH:
            cleanup_actions = self._cleanup_bash(component_id)
        elif comp_type == ComponentType.STOCK:
            cleanup_actions = self._cleanup_stock(component_id)
        

        # 移除组件
        del self._components[component_id]
        self._broadcast_delete(component_id, comp_type, comp_user_id)
        
        return {
            "success": True,
            "component_id": component_id,
            "type": comp_type,
            "cleanup_actions": cleanup_actions
        }
    
    def _to_dict(self, comp: Component) -> Dict[str, Any]:
        """组件转字典"""
        data = comp.model_dump()
        data["created_at"] = data.get("created_at", datetime.now()).isoformat()
        data["updated_at"] = data.get("updated_at", datetime.now()).isoformat()
        if data.get("last_activity"):
            data["last_activity"] = data["last_activity"].isoformat()
        if data.get("last_update"):
            data["last_update"] = data["last_update"].isoformat()
        return data
    
    # ============ 终端组件 ============
    
    def create_terminal(self, **kwargs) -> Terminal:
        """创建终端组件"""
        comp_id = self._generate_id("term")
        
        terminal = Terminal(
            id=comp_id,
            type=ComponentType.TERMINAL,
            title=kwargs.get("title", "Terminal"),
            x=kwargs.get("x", 100),
            y=kwargs.get("y", 100),
            width=kwargs.get("width", 400),
            height=kwargs.get("height", 300),
            scale=kwargs.get("scale", 1.0),
            user_id=kwargs.get("user_id"),
            session_id=kwargs.get("session_id"),
            agent_type=kwargs.get("agent_type"),
            model_id=kwargs.get("model_id"),
            status=ComponentStatus.RUNNING
        )
        
        self._components[comp_id] = terminal
        self._broadcast_create(terminal)
        return terminal
    
    def send_terminal_message(self, terminal_id: str, content: str, msg_type: str = "text") -> bool:
        """向终端发送消息"""
        terminal = self._components.get(terminal_id)
        if not terminal or terminal.type != ComponentType.TERMINAL:
            return False
        
        # 追加内容
        terminal.content += f"\n> {content}"
        terminal.lines = terminal.content.count("\n") + 1
        terminal.last_activity = datetime.now()
        terminal.updated_at = datetime.now()
        
        self._broadcast_update(terminal)
        return True
    
    def _cleanup_terminal(self, terminal_id: str) -> List[str]:
        """清理终端组件"""
        actions = []
        
        # 结束关联的终端会话
        from services.terminal_service import terminal_manager
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                asyncio.create_task(terminal_manager.destroy_session(terminal_id))
            else:
                # 否则直接运行
                loop.run_until_complete(terminal_manager.destroy_session(terminal_id))
            actions.append("session_destroyed")
        except Exception as e:
            print(f"Warning: Failed to destroy terminal session: {e}")
            actions.append("session_destroy_failed")
        
        actions.append("terminal_removed")
        return actions
    
    # ============ Bash 组件 ============
    
    async def create_bash(self, **kwargs) -> BashComponent:
        """创建并执行 Bash 命令"""
        comp_id = self._generate_id("bash")
        command = kwargs.get("command")
        
        bash_comp = BashComponent(
            id=comp_id,
            type=ComponentType.BASH,
            command=command,
            title=kwargs.get("title") or f"Bash: {command[:20]}...",
            x=kwargs.get("x") or 100,
            y=kwargs.get("y") or 100,
            width=kwargs.get("width") or 600,
            height=kwargs.get("height") or 350,
            scale=kwargs.get("scale") or 1.0,
            user_id=kwargs.get("user_id"),
            status=ComponentStatus.RUNNING,
            auto_close=kwargs.get("auto_close", True),
            auto_close_delay=kwargs.get("auto_close_delay", 3000)
        )
        
        self._components[comp_id] = bash_comp
        self._broadcast_create(bash_comp)
        
        # 异步执行命令
        timeout = kwargs.get("timeout", 120000) / 1000  # 转为秒
        asyncio.create_task(self._run_bash_command(comp_id, command, timeout))
        
        return bash_comp
    
    async def _run_bash_command(self, comp_id: str, command: str, timeout: float):
        """执行 Bash 命令"""
        bash_comp = self._components.get(comp_id)
        if not bash_comp:
            return
        
        start_time = datetime.now()
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True
            )
            self._processes[comp_id] = proc
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout
                )
                
                bash_comp.output = stdout.decode('utf-8', errors='replace')
                if stderr:
                    bash_comp.output += f"\n[stderr]\n{stderr.decode('utf-8', errors='replace')}"
                bash_comp.exit_code = proc.returncode
                bash_comp.status = ComponentStatus.COMPLETED if proc.returncode == 0 else ComponentStatus.ERROR
                
            except asyncio.TimeoutError:
                proc.kill()
                bash_comp.output = f"Command timed out after {timeout}s"
                bash_comp.exit_code = -1
                bash_comp.status = ComponentStatus.ERROR
        
        except Exception as e:
            bash_comp.output = f"Error: {str(e)}"
            bash_comp.exit_code = -1
            bash_comp.status = ComponentStatus.ERROR
        
        finally:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            bash_comp.duration = int(duration)
            bash_comp.updated_at = datetime.now()
            self._broadcast_update(bash_comp)
            
            if comp_id in self._processes:
                del self._processes[comp_id]
            
            # 自动关闭逻辑
            if bash_comp.auto_close:
                delay = bash_comp.auto_close_delay / 1000  # 转为秒
                asyncio.create_task(self._auto_close_bash(comp_id, delay))
    
    async def _auto_close_bash(self, comp_id: str, delay: float):
        """延迟自动关闭 Bash 组件"""
        await asyncio.sleep(delay)
        
        # 检查组件是否还存在
        if comp_id in self._components:
            self.delete(comp_id)
    
    def _cleanup_bash(self, bash_id: str) -> List[str]:
        """清理 Bash 组件"""
        actions = []
        
        # 终止进程
        proc = self._processes.get(bash_id)
        if proc:
            proc.kill()
            del self._processes[bash_id]
            actions.append("process_killed")
        
        # 取消任务
        task = self._tasks.get(bash_id)
        if task:
            task.cancel()
            del self._tasks[bash_id]
            actions.append("task_cancelled")
        
        return actions
    
    # ============ 股票追踪 ============
    
    def create_stock(self, **kwargs) -> StockComponent:
        """创建股票追踪组件"""
        comp_id = self._generate_id("stock")
        stock_code = kwargs.get("stock_code")
        
        stock_comp = StockComponent(
            id=comp_id,
            type=ComponentType.STOCK,
            stock_code=stock_code,
            title=kwargs.get("title", f"Stock: {stock_code}"),
            mode=kwargs.get("mode", StockMode.MINUTE),
            x=kwargs.get("x", 100),
            y=kwargs.get("y", 100),
            width=kwargs.get("width", 350),
            height=kwargs.get("height", 250),
            scale=kwargs.get("scale", 1.0),
            user_id=kwargs.get("user_id"),
            alert_high=kwargs.get("alert_high"),
            alert_low=kwargs.get("alert_low"),
            refresh_interval=kwargs.get("refresh_interval", 5000),
            status=ComponentStatus.RUNNING
        )
        
        self._components[comp_id] = stock_comp
        self._broadcast_create(stock_comp)
        
        # 启动定时更新任务
        task = asyncio.create_task(self._stock_updater(comp_id))
        self._tasks[comp_id] = task
        
        return stock_comp
    
    async def _stock_updater(self, stock_id: str):
        """股票数据定时更新"""
        from services.stock_api import fetch_stock_data
        
        while stock_id in self._components:
            stock_comp = self._components.get(stock_id)
            if not stock_comp or stock_comp.status != ComponentStatus.RUNNING:
                break
            
            # 调用新浪财经API获取实时数据
            try:
                data = await fetch_stock_data(stock_comp.stock_code)
                
                if data:
                    # 更新股票数据
                    stock_comp.stock_name = data.get("name", stock_comp.stock_name)
                    stock_comp.current_price = data.get("current_price")
                    stock_comp.change = data.get("change")
                    stock_comp.high = data.get("high")
                    stock_comp.low = data.get("low")
                    stock_comp.last_update = datetime.now()
                    stock_comp.updated_at = datetime.now()
                    
                    # 检查价格预警
                    if stock_comp.alert_high and stock_comp.current_price >= stock_comp.alert_high:
                        print(f"[Stock] 高价预警: {stock_comp.stock_code} 当前价格 {stock_comp.current_price} >= 预警价 {stock_comp.alert_high}")
                    
                    if stock_comp.alert_low and stock_comp.current_price <= stock_comp.alert_low:
                        print(f"[Stock] 低价预警: {stock_comp.stock_code} 当前价格 {stock_comp.current_price} <= 预警价 {stock_comp.alert_low}")
                else:
                    # API获取失败，使用上一次的数据或模拟数据
                    print(f"[Stock] 获取股票数据失败: {stock_comp.stock_code}, 使用上次数据")
                    
            except Exception as e:
                print(f"[Stock] 更新股票数据异常: {stock_comp.stock_code}, 错误: {e}")
            
            self._broadcast_update(stock_comp)
            
            await asyncio.sleep(stock_comp.refresh_interval / 1000)
    
    def _cleanup_stock(self, stock_id: str) -> List[str]:
        """清理股票追踪组件"""
        actions = []
        
        # 取消更新任务
        task = self._tasks.get(stock_id)
        if task:
            task.cancel()
            del self._tasks[stock_id]
            actions.append("tracking_stopped")
        
        return actions
    
    # ============ 文本组件 ============
    
    def create_text(self, **kwargs) -> TextComponent:
        """创建文本组件"""
        comp_id = self._generate_id("text")
        
        text_comp = TextComponent(
            id=comp_id,
            type=ComponentType.TEXT,
            title=kwargs.get("title", "备忘录"),
            content=kwargs.get("content", ""),
            x=kwargs.get("x", 100),
            y=kwargs.get("y", 100),
            width=kwargs.get("width", 300),
            height=kwargs.get("height", 200),
            scale=kwargs.get("scale", 1.0),
            user_id=kwargs.get("user_id"),
            status=ComponentStatus.IDLE
        )
        
        self._components[comp_id] = text_comp
        self._broadcast_create(text_comp)
        return text_comp
    
    # ============ 自定义组件 ============
    
    def create_custom(self, **kwargs) -> CustomComponent:
        """创建自定义组件"""
        comp_id = self._generate_id("custom")
        
        custom_comp = CustomComponent(
            id=comp_id,
            type=ComponentType.CUSTOM,
            title=kwargs.get("title", "Custom"),
            content=kwargs.get("content", ""),
            content_type=kwargs.get("content_type", ContentType.HTML),
            x=kwargs.get("x", 100),
            y=kwargs.get("y", 100),
            width=kwargs.get("width", 300),
            height=kwargs.get("height", 200),
            scale=kwargs.get("scale", 1.0),
            user_id=kwargs.get("user_id"),
            style=kwargs.get("style"),
            actions=kwargs.get("actions"),
            status=ComponentStatus.IDLE
        )
        
        self._components[comp_id] = custom_comp
        self._broadcast_create(custom_comp)
        return custom_comp
    
    # ============ WebSocket 广播 ============
    
    def add_ws_client(self, client, user_id: Optional[str] = None):
        """添加 WebSocket 客户端"""
        if user_id:
            if user_id not in self._ws_clients:
                self._ws_clients[user_id] = []
            self._ws_clients[user_id].append(client)
        else:
            self._ws_clients_anon.append(client)
    
    def remove_ws_client(self, client):
        """移除 WebSocket 客户端"""
        # 从 user 分组中移除
        for user_id in list(self._ws_clients.keys()):
            if client in self._ws_clients[user_id]:
                self._ws_clients[user_id].remove(client)
                if not self._ws_clients[user_id]:
                    del self._ws_clients[user_id]
                return
        # 从匿名列表中移除
        if client in self._ws_clients_anon:
            self._ws_clients_anon.remove(client)
    
    async def send_to_user(self, user_id: str, message: dict):
        """发送消息给指定 user_id 的所有连接"""
        if user_id in self._ws_clients:
            for client in self._ws_clients[user_id]:
                try:
                    await client.send_json(message)
                except:
                    pass

    async def broadcast(self, message: dict, target_user_id: Optional[str] = None):
        """广播消息
        
        Args:
            message: 消息字典
            target_user_id: 指定目标用户（None=全广播）
        """
        if target_user_id:
            # 定向发送给指定用户
            await self.send_to_user(target_user_id, message)
        else:
            # 全广播：发给所有 user 分组 + 匿名客户端
            for user_id in self._ws_clients:
                for client in self._ws_clients[user_id]:
                    try:
                        await client.send_json(message)
                    except:
                        pass
            for client in self._ws_clients_anon:
                try:
                    await client.send_json(message)
                except:
                    pass
    
    def _broadcast_create(self, comp: Component):
        """广播创建事件（按组件 user_id 定向广播）"""
        asyncio.create_task(self.broadcast({
            "type": "component_created",
            "data": self._to_dict(comp)
        }, target_user_id=comp.user_id))
    
    def _broadcast_update(self, comp: Component):
        """广播更新事件（按组件 user_id 定向广播）"""
        asyncio.create_task(self.broadcast({
            "type": "component_updated",
            "data": self._to_dict(comp)
        }, target_user_id=comp.user_id))
    
    def _broadcast_delete(self, comp_id: str, comp_type: str, target_user_id: Optional[str] = None):
        """广播删除事件"""
        asyncio.create_task(self.broadcast({
            "type": "component_deleted",
            "component_id": comp_id,
            "component_type": comp_type
        }, target_user_id=target_user_id))
    

# 全局组件管理器实例
component_manager = ComponentManager()