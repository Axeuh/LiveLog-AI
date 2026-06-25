"""
STT Session Manager - STT会话管理服务

功能：
- 管理当前活跃会话
- 会话持久化存储
- 会话切换和创建
"""

import json
import logging
import threading
import time
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置 — 从统一配置读取
from config.config import get_config
_cfg_ssm = get_config()
SESSION_FILE = Path(_cfg_ssm.SESSIONS_PATH)


@dataclass
class Session:
    """会话信息"""
    session_id: str
    title: str
    created_at: float
    last_accessed: float
    directory: str = ""
    agent_type: Optional[str] = None  # 智能体类型: voice-interaction, main-task


class STTSessionManager:
    """STT会话管理器"""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else SESSION_FILE
        self.current_session: Optional[Session] = None
        self.session_history: List[Dict[str, Any]] = []
        self._agent_sessions: Dict[str, str] = {}  # agent_type -> session_id
        self.lock = threading.RLock()
        
        # 加载持久化数据
        self._load_data()
        
    def _load_data(self):
        """从文件加载数据"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    
                # 恢复当前会话
                if data.get("current_session"):
                    self.current_session = Session(**data["current_session"])
                    
                # 恢复历史
                self.session_history = data.get("history", [])
                
                # 恢复智能体会话映射
                self._agent_sessions = data.get("agent_sessions", {})
                
                logger.info(f"会话数据加载成功: 当前会话={self.current_session.session_id if self.current_session else 'None'}, 智能体会话={list(self._agent_sessions.keys())}")
            except Exception as e:
                logger.warning(f"加载会话数据失败: {e}")
                
    def _save_data(self):
        """保存数据到文件"""
        try:
            data = {
                "current_session": asdict(self.current_session) if self.current_session else None,
                "history": self.session_history,
                "agent_sessions": self._agent_sessions,
                "updated_at": time.time()
            }
            
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug("会话数据保存成功")
        except Exception as e:
            logger.error(f"保存会话数据失败: {e}")
            
    def set_current_session(
        self, 
        session_id: str, 
        title: Optional[str] = None,
        directory: Optional[str] = None
    ) -> Session:
        """设置当前会话"""
        with self.lock:
            now = time.time()
            
            # 检查是否已存在
            existing = None
            for item in self.session_history:
                if item.get("session_id") == session_id:
                    existing = item
                    break
                    
            if existing:
                # 更新访问时间
                existing["last_accessed"] = now
                self.current_session = Session(**existing)
            else:
                # 创建新会话
                session = Session(
                    session_id=session_id,
                    title=title or f"STT会话_{session_id[:8]}",
                    created_at=now,
                    last_accessed=now,
                    directory=directory or ""
                )
                self.current_session = session
                
                # 添加到历史
                self.session_history.append(asdict(session))
                
            self._save_data()
            logger.info(f"当前会话设置为: {session_id}")
            return self.current_session
            
    def get_current_session(self) -> Optional[Session]:
        """获取当前会话"""
        with self.lock:
            if self.current_session:
                self.current_session.last_accessed = time.time()
            return self.current_session
            
    def get_session_id(self) -> Optional[str]:
        """获取当前会话ID"""
        session = self.get_current_session()
        return session.session_id if session else None
        
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话"""
        with self.lock:
            return self.session_history.copy()
            
    def switch_session(self, session_id: str) -> Optional[Session]:
        """切换到指定会话"""
        with self.lock:
            for item in self.session_history:
                if item.get("session_id") == session_id:
                    item["last_accessed"] = time.time()
                    self.current_session = Session(**item)
                    self._save_data()
                    logger.info(f"切换到会话: {session_id}")
                    return self.current_session
            return None
            
    def clear_current_session(self):
        """清除当前会话"""
        with self.lock:
            self.current_session = None
            self._save_data()
            logger.info("当前会话已清除")
            
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            return {
                "current_session": self.current_session.session_id if self.current_session else None,
                "total_sessions": len(self.session_history),
                "has_current": self.current_session is not None,
                "agent_sessions": self._agent_sessions
            }
    
    def get_agent_session(self, agent_type: str) -> Optional[str]:
        """获取智能体的会话ID"""
        with self.lock:
            return self._agent_sessions.get(agent_type)
    
    def set_agent_session(self, agent_type: str, session_id: str):
        """设置智能体的会话"""
        with self.lock:
            self._agent_sessions[agent_type] = session_id
            self._save_data()
            logger.info(f"智能体 {agent_type} 的会话设置为: {session_id}")
    
    def list_agent_sessions(self) -> Dict[str, str]:
        """列出所有智能体会话"""
        with self.lock:
            return self._agent_sessions.copy()
    
    def update_session_title(self, session_id: str, title: str) -> bool:
        """更新会话标题"""
        with self.lock:
            # 更新历史记录中的标题
            for item in self.session_history:
                if item.get("session_id") == session_id:
                    item["title"] = title
                    item["last_accessed"] = time.time()
                    
                    # 如果这是当前会话，也更新当前会话
                    if self.current_session and self.current_session.session_id == session_id:
                        self.current_session = Session(**item)
                    
                    self._save_data()
                    logger.info(f"会话标题已更新: {session_id} -> {title}")
                    return True
            return False


# 单例实例
_session_manager: Optional[STTSessionManager] = None


def get_session_manager() -> STTSessionManager:
    """获取会话管理器单例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = STTSessionManager()
    return _session_manager