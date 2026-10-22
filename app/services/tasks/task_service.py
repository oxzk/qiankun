"""任务服务。"""

from __future__ import annotations

from app.infrastructure.database.models.task import Task
from app.infrastructure.database.unit_of_work import UnitOfWork, UnitOfWorkFactory, commit_on_success
from app.services.tasks.task_scheduler import TaskScheduler
from app.schemas.task import TaskCreate, TaskUpdate
from app.shared.errors import AppError
from app.services.common.lookup import get_required
from app.services.common.pagination import PageQuery, PagedResult
from app.services.providers.provider_config_service import ProviderConfigService
from app.services.tasks.task_model_factory import TaskModelFactory
from app.services.tasks.task_schedule_calculator import TaskScheduleCalculator
from app.shared.enums import NotifyStrategy, enum_map


class TaskService:
    """任务服务。"""

    def __init__(
        self,
        provider: ProviderConfigService,
        scheduler: TaskScheduler,
        factory: TaskModelFactory | None = None,
        schedule_calculator: TaskScheduleCalculator | None = None,
        uow_factory: UnitOfWorkFactory = UnitOfWork,
    ) -> None:
        """初始化任务服务依赖。"""
        self.provider = provider
        self.scheduler = scheduler
        self._factory = factory or TaskModelFactory()
        self._schedule_calculator = schedule_calculator or TaskScheduleCalculator()
        self._uow_factory = uow_factory

    async def list_tasks(
        self,
        pagination: PageQuery,
        enabled: bool | None = None,
        provider_name: str | None = None,
        name: str | None = None,
    ) -> PagedResult[Task]:
        """分页查询任务。"""
        async with self._uow_factory() as uow:
            items, total = await uow.tasks.list_paginated(
                pagination.page,
                pagination.page_size,
                enabled,
                provider_name,
                name,
            )
        return PagedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            enums=enum_map(NotifyStrategy),
        )

    async def get_task(self, task_id: int) -> Task:
        """查询任务详情。"""
        async with self._uow_factory() as uow:
            task = await get_required(uow.tasks.get_by_id, task_id, "任务不存在")
        return task

    async def create_task(self, payload: TaskCreate) -> Task:
        """创建任务。"""
        validation = await self.provider.validate_config(
            payload.provider_name,
            payload.provider_config,
        )
        if not validation.valid:
            raise AppError(validation.error or "Provider 配置无效")
        await self._ensure_notifications_exist(payload.notification_ids)
        next_run_time = self._schedule_calculator.next_run_time_for_enabled_task(
            payload.enabled,
            payload.cron_expression,
        )
        task = self._factory.from_create(payload, next_run_time=next_run_time)
        if validation.config is not None:
            task.provider_config = validation.config
        return await commit_on_success(
            self._uow_factory,
            lambda uow: uow.tasks.create(task),
        )

    async def update_task(self, task_id: int, payload: TaskUpdate) -> Task:
        """更新任务。"""
        validation = await self.provider.validate_config(
            payload.provider_name,
            payload.provider_config,
        )
        if not validation.valid:
            raise AppError(validation.error or "Provider 配置无效")
        await self._ensure_notifications_exist(payload.notification_ids)

        async def update_existing(uow: UnitOfWork) -> Task:
            """更新已存在任务。"""
            task = await get_required(uow.tasks.get_by_id, task_id, "任务不存在")
            self._factory.apply_update(task, payload)
            if validation.config is not None:
                task.provider_config = validation.config
            task.next_run_time = self._schedule_calculator.next_run_time_for_enabled_task(
                task.enabled,
                task.cron_expression,
            )
            return await uow.tasks.update(task)

        return await commit_on_success(self._uow_factory, update_existing)

    async def _ensure_notifications_exist(self, notification_ids: list[int]) -> None:
        """确认任务引用的通知渠道存在。"""
        if not notification_ids:
            return
        async with self._uow_factory() as uow:
            existing_ids = await uow.notifications.get_existing_ids(notification_ids)
        missing_ids = [item for item in notification_ids if item not in existing_ids]
        if missing_ids:
            raise AppError(f"通知渠道不存在: {', '.join(str(item) for item in missing_ids)}")

    async def delete_task(self, task_id: int) -> None:
        """删除任务。"""
        async def delete_existing(uow: UnitOfWork) -> None:
            """删除已存在任务。"""
            task = await get_required(uow.tasks.get_by_id, task_id, "任务不存在")
            await self.scheduler.cancel_task(task_id)
            await uow.tasks.delete(task)

        await commit_on_success(self._uow_factory, delete_existing)

    async def run_task(self, task_id: int) -> bool:
        """手动执行任务。"""
        ok = await self.scheduler.execute_task_now(task_id)
        if not ok:
            raise AppError("任务不存在, 正在运行或已达并发上限")
        return True

    async def cancel_task(self, task_id: int) -> bool:
        """取消运行中任务。"""
        ok = await self.scheduler.cancel_task(task_id)
        if not ok:
            raise AppError("任务未在运行")
        return True

    async def set_enabled(self, task_id: int, enabled: bool) -> Task:
        """启用或禁用任务。"""
        async def update_enabled(uow: UnitOfWork) -> Task:
            """更新任务启用状态。"""
            task = await get_required(uow.tasks.get_by_id, task_id, "任务不存在")
            task.enabled = enabled
            task.next_run_time = self._schedule_calculator.next_run_time_for_enabled_task(
                enabled,
                task.cron_expression,
            )
            return await uow.tasks.update(task)

        return await commit_on_success(self._uow_factory, update_enabled)
