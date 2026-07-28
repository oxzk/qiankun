"""FastAPI 应用入口。"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __VERSION__
from app.bootstrap.container import ApplicationContainer
from app.bootstrap.exception_handlers import register_exception_handlers
from app.config.settings import settings
from app.infrastructure.database.session import db
from app.middleware.auth import AuthMiddleware
from app.middleware.request_log import log_requests
from app.routes import api_router
from app.shared.logger import logger

API_PREFIX = "/api"
"""API 前缀。"""


def resolve_public_dir() -> Path:
    """解析当前运行环境中的 public 静态资源目录。"""
    source_path = Path(__file__).resolve()
    for root_dir in (Path.cwd().resolve(), *source_path.parents):
        public_dir = root_dir / "public"
        if (public_dir / "index.html").is_file():
            return public_dir
    return Path.cwd().resolve() / "public"


PUBLIC_DIR = resolve_public_dir()
"""前端静态资源目录。"""

INDEX_HTML = PUBLIC_DIR / "index.html"
"""前端单页应用入口文件。"""


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """管理应用启动和关闭生命周期。"""
    logger.info("QianKun starting")
    await db.connect()
    await application.state.services.task_services.scheduler.start()
    try:
        yield
    finally:
        logger.info("QianKun shutting down")
        await application.state.services.task_services.scheduler.stop()
        await application.state.services.close()
        await db.close()


def create_app() -> FastAPI:
    """创建并组装 FastAPI 应用。"""
    application = FastAPI(
        title=settings.app_name,
        version=__VERSION__,
        debug=settings.app_debug,
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
        redirect_slashes=False,
    )
    application.state.services = ApplicationContainer()
    register_middlewares(application)
    register_routes(application)
    mount_frontend(application)
    return application


def register_middlewares(application: FastAPI) -> None:
    """注册应用中间件。"""
    application.middleware("http")(log_requests)
    application.add_middleware(AuthMiddleware)

    cors_origins = settings.cors_origins
    allow_credentials = bool(cors_origins) and "*" not in cors_origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )


def register_routes(application: FastAPI) -> None:
    """注册异常处理器和 API 路由。"""
    register_exception_handlers(application)
    application.include_router(api_router, prefix=API_PREFIX)


def mount_frontend(application: FastAPI) -> None:
    """挂载前端静态资源和单页应用入口。"""
    if not INDEX_HTML.exists():
        return

    application.mount("/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets")

    @application.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str) -> FileResponse:
        """返回前端单页应用入口。"""
        requested_file = PUBLIC_DIR / full_path
        if full_path and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(INDEX_HTML)


app = create_app()
"""FastAPI 应用实例。"""
