"""
定时任务 API 路由
提供任务管理的 RESTful API
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime

from services.task_storage import TaskStorage, get_task_storage
from services.task_executor import get_task_executor
from services.task_models import ScheduleType
import asyncio


class TaskTargetType(str, Enum):
    """任务发送目标类型"""
    MAIN_TASK = "main_task"
    CURRENT = "current"
    NEW_SESSION = "new_session"
    SPECIFIC = "specific"


class PrefixConfig(BaseModel):
    """消息前缀配置"""
    title: Optional[str] = None
    description: Optional[str] = None
    use_custom: bool = False
    speaker: Optional[str] = None
    prompt: Optional[str] = None
    message_type: Optional[str] = None
    location: Optional[str] = None


class TaskCreate(BaseModel):
    """创建任务请求"""
    task_name: str
    prompt: str
    schedule_type: ScheduleType
    schedule_config: Dict[str, Any]
    enabled: bool = True
    repeat: bool = False
    target_type: TaskTargetType = TaskTargetType.MAIN_TASK
    target_session: Optional[str] = None
    prefix_config: Optional[PrefixConfig] = None


class TaskUpdate(BaseModel):
    """更新任务请求"""
    task_name: Optional[str] = None
    prompt: Optional[str] = None
    schedule_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    repeat: Optional[bool] = None
    target_type: Optional[TaskTargetType] = None
    target_session: Optional[str] = None
    prefix_config: Optional[PrefixConfig] = None


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    user_id: str
    task_name: str
    prompt: str
    schedule_type: str
    schedule_config: Dict[str, Any]
    enabled: bool
    repeat: bool
    created_at: float
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    target_type: str = "main_task"
    target_session: Optional[str] = None
    prefix_config: Optional[Dict[str, Any]] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: List[TaskResponse]
    total: int


class TaskExecutionListResponse(BaseModel):
    """执行历史列表响应"""
    executions: List[Dict[str, Any]]
    total: int


class TaskTriggerResponse(BaseModel):
    """触发任务响应"""
    success: bool
    task_id: str
    message: str = ""

router = APIRouter(
    prefix="/tasks",
    tags=["定时任务"],
    responses={404: {"description": "任务不存在"}}
)


# ============ API 端点 ============

@router.post("", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    request: Request,
):
    storage = get_task_storage()
    # 从认证中间件获取 user_id
    user_id = getattr(request.state, 'user_id', None) or "default"
    """
    创建新定时任务
    
    - **task_name**: 任务名称（必填）
    - **prompt**: 任务提示词（必填）
    - **schedule_type**: 调度类型，delay（延时）或 scheduled（定时）（必填）
    - **schedule_config**: 调度配置（必填）
    - **enabled**: 是否启用，默认 true
    - **repeat**: 是否重复执行，默认 false
    - **target_type**: 发送目标类型，默认 main_task
    - **target_session**: 目标会话ID（当target_type为specific时必填）
    - **prefix_config**: 消息前缀配置（可选）
    """
    try:
        # 将Pydantic模型转换为字典
        prefix_config_dict = None
        if task.prefix_config:
            prefix_config_dict = task.prefix_config.model_dump()
        
        created_task = storage.create_task(
            user_id=user_id,
            task_name=task.task_name,
            prompt=task.prompt,
            schedule_type=task.schedule_type.value,
            schedule_config=task.schedule_config,
            enabled=task.enabled,
            repeat=task.repeat,
            target_type=task.target_type.value,
            target_session=task.target_session,
            prefix_config=prefix_config_dict
        )
        
        # 计算下次执行时间（不用等调度器，立即计算）
        if created_task.enabled:
            from services.task_scheduler import get_task_scheduler
            scheduler = get_task_scheduler()
            next_run = scheduler._calculate_next_run(created_task)
            if next_run:
                storage.update_task(created_task.task_id, next_run=next_run)
                created_task.next_run = next_run
        
        # 广播任务创建事件
        asyncio.create_task(_broadcast_task_event("task_created", created_task))
        
        return TaskResponse(
            task_id=created_task.task_id,
            user_id=created_task.user_id,
            task_name=created_task.task_name,
            prompt=created_task.prompt,
            schedule_type=created_task.schedule_type,
            schedule_config=created_task.schedule_config,
            enabled=created_task.enabled,
            repeat=created_task.repeat,
            created_at=created_task.created_at,
            last_run=created_task.last_run,
            next_run=created_task.next_run,
            run_count=created_task.run_count,
            target_type=created_task.target_type,
            target_session=created_task.target_session,
            prefix_config=prefix_config_dict
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    request: Request,
    enabled_only: bool = Query(False, description="只返回启用的任务"),
):
    storage = get_task_storage()
    # 从认证中间件获取 user_id
    user_id = getattr(request.state, 'user_id', None) or "default"
    """
    获取当前用户的任务列表
    
    - **enabled_only**: 是否只返回启用的任务，默认 false
    """
    try:
        if enabled_only:
            tasks = storage.get_enabled_tasks()
            # 过滤当前用户的任务
            tasks = [t for t in tasks if t.user_id == user_id]
        else:
            tasks = storage.get_user_tasks(user_id)
        
        task_responses = [
            TaskResponse(
                task_id=t.task_id,
                user_id=t.user_id,
                task_name=t.task_name,
                prompt=t.prompt,
                schedule_type=t.schedule_type,
                schedule_config=t.schedule_config,
                enabled=t.enabled,
                repeat=t.repeat,
                created_at=t.created_at,
                last_run=t.last_run,
                next_run=t.next_run,
                run_count=t.run_count,
                target_type=t.target_type,
                target_session=t.target_session,
                prefix_config=t.prefix_config
            )
            for t in tasks
        ]
        
        return TaskListResponse(
            tasks=task_responses,
            total=len(task_responses)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
):
    storage = get_task_storage()
    """
    获取指定任务的详细信息
    
    - **task_id**: 任务ID（路径参数）
    """
    task = storage.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 验证用户权限
    # if task.user_id != current_user_id:
    #     raise HTTPException(status_code=403, detail="无权访问此任务")
    
    return TaskResponse(
        task_id=task.task_id,
        user_id=task.user_id,
        task_name=task.task_name,
        prompt=task.prompt,
        schedule_type=task.schedule_type,
        schedule_config=task.schedule_config,
        enabled=task.enabled,
        repeat=task.repeat,
        created_at=task.created_at,
        last_run=task.last_run,
        next_run=task.next_run,
        run_count=task.run_count,
        target_type=task.target_type,
        target_session=task.target_session,
        prefix_config=task.prefix_config
    )


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
):
    storage = get_task_storage()
    """
    更新任务配置
    
    - **task_id**: 任务ID（路径参数）
    - **task_name**: 新的任务名称（可选）
    - **prompt**: 新的提示词（可选）
    - **schedule_config**: 新的调度配置（可选）
    - **enabled**: 是否启用（可选）
    - **repeat**: 是否重复执行（可选）
    - **target_type**: 发送目标类型（可选）
    - **target_session**: 目标会话ID（可选）
    - **prefix_config**: 消息前缀配置（可选）
    """
    # 检查任务是否存在
    existing_task = storage.get_task(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 验证用户权限
    
    # 构建更新字段
    update_fields = {}
    if task_update.task_name is not None:
        update_fields["task_name"] = task_update.task_name
    if task_update.prompt is not None:
        update_fields["prompt"] = task_update.prompt
    if task_update.schedule_config is not None:
        update_fields["schedule_config"] = task_update.schedule_config
        update_fields["next_run"] = None  # 调度器会自动重算
    if task_update.enabled is not None:
        update_fields["enabled"] = task_update.enabled
        if task_update.enabled:
            update_fields["next_run"] = None  # 重新启用时重算
    if task_update.repeat is not None:
        update_fields["repeat"] = task_update.repeat
    if task_update.target_type is not None:
        update_fields["target_type"] = task_update.target_type.value
    if task_update.target_session is not None:
        update_fields["target_session"] = task_update.target_session
    if task_update.prefix_config is not None:
        update_fields["prefix_config"] = task_update.prefix_config.model_dump()
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="没有提供要更新的字段")
    
    try:
        updated_task = storage.update_task(task_id, **update_fields)
        
        if not updated_task:
            raise HTTPException(status_code=500, detail="更新任务失败")
        
        # 广播任务更新事件
        asyncio.create_task(_broadcast_task_event("task_updated", updated_task))
        
        return TaskResponse(
            task_id=updated_task.task_id,
            user_id=updated_task.user_id,
            task_name=updated_task.task_name,
            prompt=updated_task.prompt,
            schedule_type=updated_task.schedule_type,
            schedule_config=updated_task.schedule_config,
            enabled=updated_task.enabled,
            repeat=updated_task.repeat,
            created_at=updated_task.created_at,
            last_run=updated_task.last_run,
            next_run=updated_task.next_run,
            run_count=updated_task.run_count,
            target_type=updated_task.target_type,
            target_session=updated_task.target_session,
            prefix_config=updated_task.prefix_config
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新任务失败: {str(e)}")


# ==== 辅助函数 ====

async def _broadcast_task_event(event_type: str, task):
    """广播任务事件到WebSocket客户端"""
    try:
        from services.component_manager import component_manager
        await component_manager.broadcast({
            "type": event_type,
            "task": {
                "task_id": task.task_id,
                "task_name": task.task_name,
                "schedule_type": task.schedule_type,
                "schedule_config": task.schedule_config,
                "enabled": task.enabled,
                "repeat": task.repeat,
                "last_run": task.last_run,
                "next_run": task.next_run,
                "run_count": task.run_count,
                "target_type": task.target_type,
            }
        })
    except Exception as e:
        logger.error(f"广播任务事件失败: {e}")


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
):
    storage = get_task_storage()
    """
    删除指定任务
    
    - **task_id**: 任务ID（路径参数）
    """
    # 检查任务是否存在
    existing_task = storage.get_task(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 验证用户权限
    
    try:
        success = storage.delete_task(task_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="删除任务失败")
        
        # 广播删除事件
        asyncio.create_task(_broadcast_task_event("task_deleted", existing_task))
        
        return {"success": True, "message": "任务已删除", "task_id": task_id}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")


@router.get("/{task_id}/executions", response_model=TaskExecutionListResponse)
async def get_task_executions(
    task_id: str,
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
):
    storage = get_task_storage()
    """
    获取任务的执行历史
    
    - **task_id**: 任务ID（路径参数）
    - **limit**: 返回数量限制（默认10，最大100）
    - **offset**: 偏移量（默认0）
    """
    # 检查任务是否存在
    existing_task = storage.get_task(task_id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 验证用户权限
    
    try:
        executions = storage.get_execution_history(task_id, limit=limit, offset=offset)
        
        execution_responses = [
            {
                "execution_id": e.execution_id,
                "task_id": e.task_id,
                "status": e.status,
                "session_id": e.session_id,
                "started_at": e.started_at,
                "completed_at": e.completed_at,
                "retry_count": e.retry_count,
                "error_message": e.error_message
            }
            for e in executions
        ]
        
        return TaskExecutionListResponse(
            executions=execution_responses,
            total=len(execution_responses)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")


@router.post("/{task_id}/trigger", response_model=TaskTriggerResponse)
async def trigger_task(
    task_id: str,
):
    storage = get_task_storage()
    executor = get_task_executor()
    """
    手动触发任务执行
    
    立即执行任务，不等待定时触发
    
    - **task_id**: 任务ID（路径参数）
    """
    # 检查任务是否存在
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # TODO: 验证用户权限
    
    try:
        # 立即执行任务
        success = await executor.execute_task_now(task)
        
        if success:
            # 手动触发也记录执行记录
            storage.record_execution(
                task_id=task_id,
                status="success"
            )
            # 广播任务执行事件
            task_after = storage.get_task(task_id)
            if task_after:
                asyncio.create_task(_broadcast_task_event("task_executed", task_after))
            return TaskTriggerResponse(
                success=True,
                task_id=task_id,
                message="任务已手动触发并执行成功"
            )
        else:
            return TaskTriggerResponse(
                success=False,
                task_id=task_id,
                message="任务执行失败，请查看执行历史了解详情"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"触发任务失败: {str(e)}")


@router.get("/stats/overview")
async def get_task_stats(
):
    storage = get_task_storage()
    """
    获取任务统计信息
    
    返回全局任务统计数据
    """
    try:
        total_tasks = storage.count_tasks()
        enabled_tasks = storage.count_enabled_tasks()
        storage_size = storage.get_storage_size()
        
        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "disabled_tasks": total_tasks - enabled_tasks,
            "storage_size_bytes": storage_size["total"],
            "tasks_file_size": storage_size["tasks_file"],
            "executions_file_size": storage_size["executions_file"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")