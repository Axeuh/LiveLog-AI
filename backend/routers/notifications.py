"""手机 App 通知推送路由

AI 通过工具向用户手机发送系统通知，App 轮询获取后显示。
"""

import time
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["通知推送"])

# ── 内存通知队列 ──
# user_id -> [{id, title, content, created_at}]
_notification_queue: Dict[str, list] = {}
_notification_history: Dict[str, list] = {}
MAX_HISTORY_PER_USER = 100
_next_id = 0


# ── 请求/响应模型 ──

class NotificationSendRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="通知标题")
    content: str = Field(..., max_length=2000, description="通知内容")
    user_id: Optional[str] = Field(None, description="目标用户，不传则发给当前用户")


class NotificationItem(BaseModel):
    id: int
    title: str
    content: str
    created_at: int  # unix timestamp


class NotificationPollResponse(BaseModel):
    notifications: List[NotificationItem]


class NotificationHistoryResponse(BaseModel):
    notifications: List[NotificationItem]
    total: int


# ── API 端点 ──

@router.post("/notification/send", response_model=dict)
async def send_notification(req: NotificationSendRequest, request: Request):
    """AI 调用此接口给用户手机发送系统通知"""
    user_id = req.user_id or getattr(request.state, "user_id", None) or "default"
    notification = {
        "id": _get_next_id(),
        "title": req.title,
        "content": req.content,
        "created_at": int(time.time()),
    }
    _notification_queue.setdefault(user_id, []).append(notification)
    _history = _notification_history.setdefault(user_id, [])
    _history.append(notification)
    # auto-prune oldest
    if len(_history) > MAX_HISTORY_PER_USER:
        _history[:len(_history) - MAX_HISTORY_PER_USER] = []
    logger.info(f"[Notification] 发送通知 user={user_id}: {req.title}")
    return {"status": "ok", "notification_id": notification["id"]}


@router.get("/notification/poll", response_model=NotificationPollResponse)
async def poll_notifications(request: Request):
    """手机 App 轮询获取待处理通知（获取后自动清除）"""
    user_id = getattr(request.state, "user_id", None) or "default"
    notifications = _notification_queue.pop(user_id, [])
    if notifications:
        logger.info(f"[Notification] 推送 {len(notifications)} 条通知给 user={user_id}")
    return {"notifications": notifications}


@router.get("/notification/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取通知历史（分页，按时间倒序）"""
    user_id = getattr(request.state, "user_id", None) or "default"
    history = _notification_history.get(user_id, [])
    total = len(history)
    page = list(reversed(history))[offset:offset + limit]
    return {"notifications": page, "total": total}


@router.delete("/notification/history/{notification_id}", response_model=dict)
async def delete_notification(notification_id: int, request: Request):
    """删除指定通知历史记录"""
    user_id = getattr(request.state, "user_id", None) or "default"
    history = _notification_history.get(user_id, [])
    for i, n in enumerate(history):
        if n["id"] == notification_id:
            history.pop(i)
            return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Notification not found")


# ── 内部工具 ──

def _get_next_id() -> int:
    global _next_id
    _next_id += 1
    return _next_id
