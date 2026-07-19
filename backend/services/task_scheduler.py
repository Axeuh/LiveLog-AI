"""
定时任务调度器
负责定期检查并执行到期的定时任务
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Any
from enum import Enum

from .task_storage import TaskStorage, get_task_storage
from .task_models import Task, TaskExecutionState
from .schedule_parser import ScheduleParser
from .task_config import (
    TASK_SCHEDULER_CHECK_INTERVAL,
    TASK_MAX_CONCURRENT,
    RECOVERY_EXECUTION_TIMEOUT
)

logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    定时任务调度器
    
    功能：
    - 每2秒检查一次所有启用的任务
    - 自动计算下次执行时间
    - 支持延时任务（delay）和定时任务（scheduled）
    - 崩溃恢复机制
    - 并发控制
    """
    
    def __init__(
        self,
        task_storage: Optional[TaskStorage] = None,
        execute_callback: Optional[Callable[[Task], Any]] = None,
        check_interval: int = TASK_SCHEDULER_CHECK_INTERVAL
    ):
        """
        初始化调度器
        
        Args:
            task_storage: 任务存储实例
            execute_callback: 任务执行回调函数
            check_interval: 检查间隔（秒）
        """
        self.storage = task_storage or get_task_storage()
        self.execute_callback = execute_callback
        self.check_interval = check_interval
        
        # 运行状态
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
        # 并发控制
        self._semaphore = asyncio.Semaphore(TASK_MAX_CONCURRENT)
        
        # 正在执行的任务ID集合（防止重复执行）
        self._executing_tasks: set = set()
        
        logger.info("TaskScheduler 初始化完成")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            logger.warning("调度器已在运行")
            return
        
        self._running = True
        
        # 启动时恢复卡住的任务
        await self._recover_stuck_executions()
        
        # 启动调度循环
        self._task = asyncio.create_task(self._scheduler_loop())
        
        # 启动 YAML 兜底修复监控
        self.storage.start_repair_monitor()
        
        logger.info(f"定时任务调度器已启动（检查间隔: {self.check_interval}秒）")
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("定时任务调度器已停止")
    
    async def _scheduler_loop(self) -> None:
        """
        调度器主循环
        
        每 check_interval 秒检查一次所有启用的任务
        """
        while self._running:
            try:
                await self._check_tasks()
            except Exception as e:
                logger.error(f"任务检查失败: {e}", exc_info=True)
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_tasks(self) -> None:
        """检查并执行到期的任务"""
        now = datetime.now().timestamp()
        
        # 获取所有启用的任务
        tasks = self.storage.get_enabled_tasks()
        
        due_tasks = []
        for task in tasks:
            # 跳过正在执行的任务
            if task.task_id in self._executing_tasks:
                continue
            
            # 计算下次执行时间（如果未计算）
            if task.next_run is None:
                task.next_run = self._calculate_next_run(task)
                if task.next_run:
                    self.storage.update_task(task.task_id, next_run=task.next_run)
            
            # 检查是否到期
            if task.next_run and task.next_run <= now:
                due_tasks.append(task)
        
        # 执行到期的任务
        for task in due_tasks:
            # 使用信号量控制并发
            asyncio.create_task(self._execute_with_semaphore(task))
    
    async def _execute_with_semaphore(self, task: Task) -> None:
        """
        使用信号量控制并发执行任务
        """
        async with self._semaphore:
            await self._execute_task(task)
    
    async def _execute_task(self, task: Task) -> None:
        """
        执行单个任务
        
        Args:
            task: 要执行的任务
        """
        if task.task_id in self._executing_tasks:
            logger.warning(f"任务 {task.task_id} 正在执行中，跳过")
            return
        
        self._executing_tasks.add(task.task_id)
        
        try:
            now = datetime.now().timestamp()
            
            # 更新任务状态
            task.last_run = now
            task.run_count += 1
            
            # 延时任务执行后自动禁用（支持新 schedule 字段）
            is_delay = task.schedule_type == "delay"
            if not is_delay and task.schedule is not None:
                try:
                    is_delay = ScheduleParser.parse(task.schedule).mode == "delay"
                except Exception:
                    pass
            if is_delay:
                task.enabled = False
            
            # 计算下次执行时间
            if task.repeat and task.enabled:
                task.next_run = self._calculate_next_run(task)
            else:
                task.next_run = None
            
            # 保存状态
            self.storage.update_task(
                task.task_id,
                last_run=task.last_run,
                run_count=task.run_count,
                enabled=task.enabled,
                next_run=task.next_run
            )
            
            # 创建执行记录
            execution = self.storage.record_execution(
                task_id=task.task_id,
                status="executing"
            )
            
            logger.info(f"开始执行任务: {task.task_id} - {task.task_name}")
            
            # 广播任务执行事件
            await self._broadcast_task_event("task_executed", task)
            
            # 调用执行回调
            if self.execute_callback:
                try:
                    await self.execute_callback(task)
                    
                    # 更新执行记录为成功
                    execution.status = "success"
                    execution.completed_at = datetime.now().timestamp()
                    self.storage.update_execution(execution)
                    
                    logger.info(f"任务执行成功: {task.task_id}")
                    
                except Exception as e:
                    # 更新执行记录为失败
                    execution.status = "failed"
                    execution.completed_at = datetime.now().timestamp()
                    execution.error_message = str(e)
                    self.storage.update_execution(execution)
                    
                    logger.error(f"任务执行失败: {task.task_id} - {e}")
            
        except Exception as e:
            logger.error(f"执行任务时出错: {task.task_id} - {e}", exc_info=True)
        
        finally:
            self._executing_tasks.discard(task.task_id)
    
    def _calculate_next_run(self, task: Task) -> Optional[float]:
        """
        计算任务下次执行时间
        
        Args:
            task: 任务对象
            
        Returns:
            下次执行时间戳，None 如果不需要再执行
        """
        now = datetime.now()
        
        # NEW: 如果有 schedule 字段，优先使用 ScheduleParser
        if task.schedule is not None:
            config = ScheduleParser.parse(task.schedule)
            if config.mode != "invalid":
                next_time = config.next_run_time(now)
                if next_time:
                    return next_time.timestamp()
            # 解析失败则回退到旧方法
        
        if task.schedule_type == "delay":
            # 延时任务：从创建时间 + 延迟
            config = task.schedule_config
            delay_seconds = (
                config.get("seconds", 0) +
                config.get("minutes", config.get("delay_minutes", 0)) * 60 +
                config.get("hours", config.get("delay_hours", 0)) * 3600 +
                config.get("days", 0) * 86400 +
                config.get("weeks", 0) * 604800 +
                config.get("months", 0) * 2592000  # 30天
            )
            
            if delay_seconds <= 0:
                return None
            
            # 如果任务从未执行过，从创建时间计算
            # 否则不重新计算（延时任务只执行一次）
            if task.run_count == 0:
                return task.created_at + delay_seconds
            else:
                return None
        
        elif task.schedule_type == "scheduled":
            config = task.schedule_config
            mode = config.get("mode", "daily")  # 默认按天
            
            if mode == "daily":
                return self._calculate_daily_next_run(config, now, task.last_run)
            elif mode == "weekly":
                return self._calculate_weekly_next_run(config, now, task.last_run)
            elif mode == "monthly":
                return self._calculate_monthly_next_run(config, now, task.last_run)
            elif mode == "yearly":
                return self._calculate_yearly_next_run(config, now, task.last_run)
        
        return None
    
    def _calculate_daily_next_run(
        self,
        config: Dict[str, Any],
        now: datetime,
        last_run: Optional[float]
    ) -> Optional[float]:
        """
        计算每天任务下次执行时间
        
        Args:
            config: 配置 {mode: "daily", hour: 9, minute: 0}
            now: 当前时间
            last_run: 上次执行时间
            
        Returns:
            下次执行时间戳
        """
        hour = config.get("hour", 0)
        minute = config.get("minute", 0)
        
        # 今天的目标时间
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天的时间已过，明天
        if target <= now:
            target += timedelta(days=1)
        
        return target.timestamp()
    
    def _calculate_weekly_next_run(
        self, 
        config: Dict[str, Any], 
        now: datetime,
        last_run: Optional[float]
    ) -> Optional[float]:
        """
        计算每周任务下次执行时间
        
        Args:
            config: 配置 {mode: "weekly", days: [1,2,3,4,5], hour: 9, minute: 0}
            now: 当前时间
            last_run: 上次执行时间
            
        Returns:
            下次执行时间戳
        """
        days = config.get("days", [])
        hour = config.get("hour", 0)
        minute = config.get("minute", 0)
        
        if not days:
            return None
        
        # 从当前时间开始查找
        current = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天的时间已过，从明天开始
        if current <= now:
            current = current + timedelta(days=1)
        
        # 查找下一个符合条件的星期
        for _ in range(7):  # 最多查7天
            if current.weekday() + 1 in days:  # weekday() 返回 0-6，days 是 1-7
                return current.timestamp()
            current = current + timedelta(days=1)
        
        return None
    
    def _calculate_monthly_next_run(
        self,
        config: Dict[str, Any],
        now: datetime,
        last_run: Optional[float]
    ) -> Optional[float]:
        """
        计算每月任务下次执行时间
        支持单日或多日：
        - {mode: "monthly", day: 1, hour: 8, minute: 0}
        - {mode: "monthly", days: [1, 15], hour: 8, minute: 0}
        """
        hour = config.get("hour", 0)
        minute = config.get("minute", 0)
        days = config.get("days", [])
        if not days:
            single_day = config.get("day")
            if single_day:
                days = [single_day]
        if not days:
            return None
        
        year, month = now.year, now.month
        for _ in range(12):
            for day in sorted(days):
                try:
                    target = datetime(year, month, day, hour, minute, 0)
                    if target > now:
                        return target.timestamp()
                except ValueError:
                    continue
            month += 1
            if month > 12:
                month = 1
                year += 1
        return None
    
    def _calculate_yearly_next_run(
        self,
        config: Dict[str, Any],
        now: datetime,
        last_run: Optional[float]
    ) -> Optional[float]:
        """
        计算每年任务下次执行时间
        支持单日或多日：
        - {mode: "yearly", month: 1, day: 1, hour: 0, minute: 0}
        - {mode: "yearly", dates: [{"month":1,"day":1}, {"month":12,"day":25}], hour: 9, minute: 0}
        """
        hour = config.get("hour", 0)
        minute = config.get("minute", 0)
        
        # 支持 dates 数组
        dates = config.get("dates", [])
        if not dates:
            single_month = config.get("month")
            single_day = config.get("day")
            if single_month and single_day:
                dates = [{"month": single_month, "day": single_day}]
        if not dates:
            return None
        
        for _ in range(3):  # 最多查3年
            for entry in sorted(dates, key=lambda x: (x["month"], x["day"])):
                try:
                    y = now.year
                    target = datetime(y, entry["month"], entry["day"], hour, minute, 0)
                    if target > now:
                        return target.timestamp()
                except ValueError:
                    continue
            now = now.replace(year=now.year + 1)
        
        return None
    
    async def _recover_stuck_executions(self) -> None:
        """
        恢复上次崩溃时卡住的任务
        
        将状态为 "executing" 且超时的执行记录标记为失败
        """
        try:
            stuck_executions = self.storage.get_executions_by_state(
                TaskExecutionState.EXECUTING,
                started_before=datetime.now().timestamp() - RECOVERY_EXECUTION_TIMEOUT
            )
            
            recovered_count = 0
            for execution in stuck_executions:
                execution.status = "failed"
                execution.completed_at = datetime.now().timestamp()
                execution.error_message = "系统崩溃恢复 - 执行超时"
                
                if self.storage.update_execution(execution):
                    recovered_count += 1
                    logger.warning(f"恢复卡住的执行记录: {execution.execution_id}")
            
            if recovered_count > 0:
                logger.info(f"共恢复 {recovered_count} 条卡住的执行记录")
        
        except Exception as e:
            logger.error(f"恢复卡住任务失败: {e}")
    
    async def _broadcast_task_event(self, event_type: str, task) -> None:
        """广播任务事件到WebSocket客户端"""
        try:
            from services.component_manager import component_manager
            task_dict = {
                "task_id": task.task_id,
                "task_name": task.task_name,
                "schedule_type": task.schedule_type,
                "schedule_config": task.schedule_config,
                "schedule": task.schedule,
                "enabled": task.enabled,
                "repeat": task.repeat,
                "last_run": task.last_run,
                "next_run": task.next_run,
                "run_count": task.run_count,
                "target_type": task.target_type,
            }
            await component_manager.broadcast({
                "type": event_type,
                "task": task_dict
            })
        except Exception as e:
            logger.error(f"广播任务事件失败: {e}")
    
    def is_running(self) -> bool:
        """检查调度器是否正在运行"""
        return self._running
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            状态信息字典
        """
        return {
            "running": self._running,
            "check_interval": self.check_interval,
            "max_concurrent": TASK_MAX_CONCURRENT,
            "current_executing": len(self._executing_tasks),
            "executing_tasks": list(self._executing_tasks)
        }


# 全局单例
_task_scheduler_instance: Optional[TaskScheduler] = None


def get_task_scheduler() -> TaskScheduler:
    """获取 TaskScheduler 单例"""
    global _task_scheduler_instance
    if _task_scheduler_instance is None:
        _task_scheduler_instance = TaskScheduler()
    return _task_scheduler_instance


def init_task_scheduler(
    task_storage: Optional[TaskStorage] = None,
    execute_callback: Optional[Callable[[Task], Any]] = None
) -> TaskScheduler:
    """
    初始化 TaskScheduler
    
    Args:
        task_storage: 任务存储实例
        execute_callback: 执行回调函数
        
    Returns:
        TaskScheduler 实例
    """
    global _task_scheduler_instance
    _task_scheduler_instance = TaskScheduler(task_storage, execute_callback)
    return _task_scheduler_instance