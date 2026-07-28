"""任务领域服务装配。"""

from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.database.unit_of_work import UnitOfWorkFactory
from app.services.executions.execution_lifecycle_service import ExecutionLifecycleService
from app.services.notifications.notification_dispatch_service import NotificationDispatchService
from app.services.providers.provider_config_service import ProviderConfigService
from app.services.providers.provider_execution_service import ProviderExecutionService
from app.services.tasks.task_attempt_executor import TaskAttemptExecutor
from app.services.tasks.task_model_factory import TaskModelFactory
from app.services.tasks.task_retry_policy import TaskRetryPolicy
from app.services.tasks.task_run_finalizer import TaskRunFinalizer
from app.services.tasks.task_runner import TaskRunner
from app.services.tasks.task_schedule_calculator import TaskScheduleCalculator
from app.services.tasks.task_schedule_policy import SchedulePolicy
from app.services.tasks.task_service import TaskService
from app.services.tasks.task_scheduler import TaskScheduler


@dataclass(slots=True)
class TaskServices:
    """任务领域服务集合。"""

    runner: TaskRunner
    scheduler: TaskScheduler
    service: TaskService


def build_task_services(
    provider_config: ProviderConfigService,
    provider_execution: ProviderExecutionService,
    execution_lifecycle: ExecutionLifecycleService,
    notification_dispatch: NotificationDispatchService,
    uow_factory: UnitOfWorkFactory,
) -> TaskServices:
    """构造任务领域服务集合。"""
    factory = TaskModelFactory()
    schedule_calculator = TaskScheduleCalculator()
    schedule_policy = SchedulePolicy(uow_factory=uow_factory)
    attempt_executor = TaskAttemptExecutor(
        provider=provider_execution,
        executions=execution_lifecycle,
    )
    retry_policy = TaskRetryPolicy()
    finalizer = TaskRunFinalizer(
        notifications=notification_dispatch,
        uow_factory=uow_factory,
    )
    runner = TaskRunner(
        provider=provider_execution,
        executions=execution_lifecycle,
        notifications=notification_dispatch,
        attempt_executor=attempt_executor,
        retry_policy=retry_policy,
        finalizer=finalizer,
        uow_factory=uow_factory,
    )
    scheduler = TaskScheduler(
        planner=schedule_policy,
        runner=runner,
        executions=execution_lifecycle,
        uow_factory=uow_factory,
    )
    service = TaskService(
        provider=provider_config,
        scheduler=scheduler,
        factory=factory,
        schedule_calculator=schedule_calculator,
        uow_factory=uow_factory,
    )
    return TaskServices(
        runner=runner,
        scheduler=scheduler,
        service=service,
    )
