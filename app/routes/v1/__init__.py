"""V1 API 路由导出。"""

from fastapi import APIRouter

from app.routes.v1.auth import router as auth_router
from app.routes.v1.backups import router as backups_router
from app.routes.v1.executions import router as executions_router
from app.routes.v1.health import router as health_router
from app.routes.v1.notifications import router as notifications_router
from app.routes.v1.providers import router as providers_router
from app.routes.v1.stats import router as stats_router
from app.routes.v1.tasks import router as tasks_router

api_router = APIRouter()
"""V1 API 根路由。"""

for router in [
    health_router,
    auth_router,
    backups_router,
    providers_router,
    tasks_router,
    executions_router,
    notifications_router,
    stats_router,
]:
    api_router.include_router(router)
