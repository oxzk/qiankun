# Qiankun

基于 anvil 架构分层 + qiankun.1 调度核心的 **Cron 定时任务调度服务**。

Python 3.12 · FastAPI · SQLAlchemy 2 Async · PostgreSQL · Alembic · croniter · Playwright (CDP)

## 架构

```
API → Application Service → Scheduler/Provider Registry → Provider (经 Runtime 能力)
数据库: API → Application Service → UnitOfWork → Repository → Model → PostgreSQL
```

- `app/core` 配置/异常/工具（零依赖）
- `app/api` 路由 + Schema + 纯 ASGI 中间件（JWT/CORS/RequestID）+ 统一响应信封
- `app/application` 服务编排 + Composition Root（`container.py` 手动 DI）+ 调度引擎
- `app/runtime` 领域契约：Provider/Browser/Notification 抽象 + SSE 日志流（零第三方依赖）
- `app/infrastructure` 第三方库唯一入口：CDP 驱动/JWT/HTTP/loguru/通知驱动
- `app/providers` 业务插件（`pkgutil` 目录扫描自动发现，零注册代码）

## 调度模型

DB 轮询（默认 5s）+ `tasks.next_run_time` 预计算 + 事务内乐观锁 CAS 抢占
（`UPDATE ... WHERE next_run_time = 旧值`）→ fire-and-forward 执行。
停机错过的触发点直接跳过，不补跑。单实例由 PostgreSQL advisory lock 强制。

执行链路：Scheduler（并发闸门/同任务互斥）→ Policy（CAS 抢占）→ Runner（重试循环，
每次 attempt 独立执行记录，trigger_type=2 retry）→ Attempt（asyncio.timeout + shield
保护终态持久化）→ Finalizer（last_run_time + 通知分发）。

执行状态机：`0 pending → 1 running → 2 completed | 3 failed | 4 cancelled | 5 timeout`。

## 实时日志

`GET /api/v1/executions/{id}/logs/stream` (SSE)：先订阅再回放历史，空闲 20s 心跳，
终态帧后自动结束。慢客户端溢出即踢（重连读历史）。终态时日志持久化到 `task_executions.logs`。

## 快速开始

```bash
uv sync --locked
cp .env.example .env        # 配置 DATABASE_URL + JWT_SECRET
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

打开 http://127.0.0.1:8000/docs 使用 Swagger UI。默认管理员 `admin/admin`（存于
system_settings 的 auth/admin，Argon2id 散列，可经 /auth/change-password 修改）。

## 配置

环境变量无项目前缀，嵌套用 `__` 分隔（见 `.env.example`）：
`DATABASE_URL`、`JWT_SECRET`、`SCHEDULER__INTERVAL_SECONDS`、`SCHEDULER__MAX_CONCURRENT_TASKS`、
`RUNTIME__DEFAULT_TIMEOUT`、`LOGGING__*`、`CORS_ORIGINS`。

运行时可变配置（管理员凭证、CDP 端点、通知渠道、日志策略）存 `system_settings` 表，
经 API 热更新。通知渠道即 `scope=notification` 的行（telegram/webhook），
任务通过 `notification_config`（`{"channels": [...], "strategy": 0|1|2|3}`）引用。

## 新增任务类型

在 `app/providers/<name>/` 下放 `main.py`（BaseProvider 子类，声明
`name`/`config_schema`/`capabilities`）和 `config.py`（Pydantic 配置），重启即被
`pkgutil.walk_packages` 扫描发现，无需注册代码。

声明 `capabilities={"browser"}` 的 Provider 执行时会通过 `ctx.browser` 拿到
`BrowserContext`（提供 `new_page()` / `cdp_connection()`），底层由 `browser/cdp`
系统配置中的远程 CDP 端点驱动。

## 测试

```bash
uv run pytest
uv run ruff check app tests
uv run mypy app
```
