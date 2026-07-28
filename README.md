# QianKun

QianKun 是一个基于 FastAPI, SQLAlchemy Async 和 aiomysql 的定时任务调度服务, 用于按 Cron 表达式调度 Provider 任务, 记录执行审计, 并通过通知渠道发送任务结果。

项目包含后端 API, 内置 Provider 插件, Alembic 数据库迁移和 Vite + React 前端。前端构建后会输出到根目录 `public`, 后端会自动挂载静态资源并提供单页应用入口。

## 功能

- 任务管理: 创建, 更新, 删除, 启用, 禁用和手动运行 Cron 任务。
- Provider 管理: 自动发现内置 Provider, 同步到数据库, 校验配置, 测试运行。
- 执行控制: 同一任务同一时间只运行一个实例, 支持取消, 超时, 重试和状态流转。
- 审计查询: 分页查询任务执行记录, 查看执行详情和失败原因。
- 通知管理: 配置通知渠道, 测试通知发送, 按任务策略分发通知。
- 认证与安全: 管理员登录, JWT 鉴权, 首次登录强制修改默认密码。
- 备份恢复: 通过 API 创建备份并按文件名恢复。
- 前端控制台: 提供任务, Provider, 执行记录, 通知和统计页面。

## 技术栈

- Python >= 3.11
- FastAPI
- SQLAlchemy Async
- aiomysql
- Alembic
- Pydantic v2
- Vite
- React 18
- TypeScript
- Tailwind CSS

## 目录

```text
.
├── app/                    # 后端源码 (Python 包)
│   ├── main.py             # FastAPI 应用入口
│   ├── bootstrap/          # 依赖容器, Depends 注入与异常处理
│   ├── middleware/         # 鉴权与请求日志中间件
│   ├── config/             # 配置读取
│   ├── infrastructure/     # 数据库, HTTP, Provider, 通知和安全基础设施
│   ├── provider_plugins/   # Provider 插件契约和内置 Provider
│   ├── routes/             # API 路由
│   ├── schemas/            # Pydantic 请求和响应模型
│   ├── services/           # 业务服务
│   └── shared/             # 公共工具, 枚举和错误类型
├── src/                    # React 前端应用
├── migrations/             # Alembic 迁移脚本
└── public/                 # 前端构建产物挂载目录
```

## 配置

从示例文件创建本地配置:

```bash
cp .env.example .env
```

主要环境变量:

| 变量 | 说明 |
| --- | --- |
| `APP_NAME` | 应用名称, 默认 `QianKun` |
| `APP_DEBUG` | 是否启用调试模式; 生产必须为 `false` |
| `DATABASE_URL` | 数据库连接字符串, 例如 `mysql+aiomysql://user:password@localhost:3306/qiankun` |
| `DATABASE_SSL_ENABLED` | 是否启用数据库 SSL, 默认 `false` |
| `DATABASE_POOL_SIZE` | 连接池大小, 默认 `5` |
| `JWT_SECRET_KEY` | JWT 签名密钥; 生产环境禁止使用默认值 |
| `JWT_EXPIRE_HOURS` | JWT 过期小时数 |
| `CORS_ORIGINS` | 允许跨域的前端来源 JSON 数组, 默认空 |
| `SCHEDULER_INTERVAL_SECONDS` | 调度轮询间隔秒数, 默认 `5` |
| `SCHEDULER_MAX_CONCURRENT_TASKS` | 单实例最大并发任务数, 默认 `10` |
| `LOGIN_RATE_LIMIT_ATTEMPTS` | 登录失败次数上限, 默认 `5` |
| `LOGIN_RATE_LIMIT_WINDOW_SECONDS` | 登录失败计数窗口秒数, 默认 `300` |
| `PROVIDER_CODE_SANDBOX` | 是否启用动态 Provider 代码沙箱, 默认 `true` |
| `HTTP_RETRY_ATTEMPTS` | HTTP Provider 请求重试次数 |
| `HTTP_RETRY_DELAY_SECONDS` | HTTP Provider 初始重试间隔 |
| `HTTP_RETRY_BACKOFF` | HTTP Provider 重试退避倍率 |

## 后端启动

安装依赖:

```bash
uv sync
```

执行数据库迁移:

```bash
uv run alembic -c alembic.ini upgrade head
```

启动 API 服务:

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

服务启动后可访问:

- API 健康检查: `http://127.0.0.1:8000/api/health`
- OpenAPI JSON: `http://127.0.0.1:8000/api/openapi.json`

初始迁移会创建默认管理员:

- 用户名: `admin`
- 密码: `admin`

首次登录后必须修改默认密码。

## 前端启动

安装前端依赖:

```bash
cd src
npm install
```

启动开发服务:

```bash
npm run dev
```

构建生产静态资源:

```bash
npm run build
```

构建产物默认输出到 `src/dist`. 部署时拷贝到根目录 `public`, 后端会在存在 `public/index.html` 时自动挂载前端页面.

## CLI

列出内置 Provider:

```bash
uv run qiankun --list
```

同步内置 Provider 到数据库:

```bash
uv run qiankun sync
```

运行指定 Provider:

```bash
uv run qiankun run-provider probe --config '{"accounts":[{"name":"main","url":"https://example.com"}]}'
```

`--config` 必须是 JSON 对象。

## API

所有业务接口默认挂载在 `/api` 前缀下。

| 资源 | 接口 |
| --- | --- |
| 健康检查 | `GET /api/health` |
| 认证 | `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/change-password` |
| Provider | `GET /api/providers`, `POST /api/providers`, `POST /api/providers/sync`, `GET /api/providers/{provider_name}`, `PUT /api/providers/{provider_name}`, `POST /api/providers/{provider_name}/enable`, `POST /api/providers/{provider_name}/disable`, `GET /api/providers/{provider_name}/config`, `POST /api/providers/{provider_name}/validate-config`, `POST /api/providers/{provider_name}/test-run` |
| 任务 | `GET /api/tasks`, `POST /api/tasks`, `GET /api/tasks/{task_id}`, `PUT /api/tasks/{task_id}`, `DELETE /api/tasks/{task_id}`, `POST /api/tasks/{task_id}/run`, `POST /api/tasks/{task_id}/cancel`, `POST /api/tasks/{task_id}/enable`, `POST /api/tasks/{task_id}/disable` |
| 执行记录 | `GET /api/executions`, `GET /api/executions/{execution_id}` |
| 通知 | `GET /api/notifications`, `POST /api/notifications`, `PUT /api/notifications/{notification_id}`, `DELETE /api/notifications/{notification_id}`, `POST /api/notifications/{notification_id}/test` |
| 备份 | `GET /api/backups`, `POST /api/backups`, `POST /api/backups/{filename}/restore` |
| 统计 | `GET /api/stats` |

## 数据库迁移

项目使用 Alembic 管理数据库结构, 迁移脚本目录为 `migrations/versions`。

升级到最新版本:

```bash
uv run alembic -c alembic.ini upgrade head
```

修改模型后生成迁移:

```bash
uv run alembic -c alembic.ini revision --autogenerate -m "说明"
```

提交迁移时必须包含 `migrations/versions` 下的新版本文件。

## 验证

后端语法检查:

```bash
uv run python -m compileall app
```

前端构建检查:

```bash
cd src
npm run build
```
