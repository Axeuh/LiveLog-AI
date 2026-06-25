"""
存储服务模块

包含:
- PostgreSQLStorage: 元数据和关系存储
- FileStorage: 图文件备份
- base: 数据类和抽象接口定义
"""

# 基类和数据类
from .base import (
    BaseStorage,
    ThoughtNode,
    ThoughtEdge,
    MemoryEntry,
    SessionInfo,
    NodeType,
    EdgeRelation,
    ImportanceLevel,
    DisplayState,
    SessionType,
    SessionStatus,
    MemoryType
)

# 存储实现（可选导入，失败不阻塞）
try:
    from .pg_storage import PostgreSQLStorage, get_pg_storage
except ImportError as e:
    import logging
    logging.warning(f"PostgreSQL存储不可用: {e}")
    PostgreSQLStorage = None
    get_pg_storage = None

from .file_storage import FileStorage, file_storage

__all__ = [
    # 基类和数据类
    "BaseStorage",
    "ThoughtNode",
    "ThoughtEdge",
    "MemoryEntry",
    "SessionInfo",
    "NodeType",
    "EdgeRelation",
    "ImportanceLevel",
    "DisplayState",
    "SessionType",
    "SessionStatus",
    "MemoryType",
    # 存储实现（可能为None）
    "PostgreSQLStorage",
    "get_pg_storage",
    "FileStorage",
    "file_storage",
]