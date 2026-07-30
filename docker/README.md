# QianKun Docker

## 构建

从仓库根目录执行:

```bash
docker build -f docker/Dockerfile -t qiankun:local .
```

`docker/Dockerfile.dockerignore` 会在使用 `-f docker/Dockerfile` 构建时生效。若使用较旧 Docker 版本, 请确认其支持 Dockerfile-specific ignore file。

## 运行 API

```bash
docker run --rm \
  --env-file .env \
  -p 8000:8000 \
  qiankun:local
```

默认端口:

| 端口 | 说明 |
| --- | --- |
| `8000` | API 和前端静态页面 |
| `22` | OpenSSH Server |

## SSH

默认 SSH 用户名为 `root`, 密码为 `12345678`. 启动容器时必须通过 `SSH_PASSWORD` 设置生产密码:

```bash
docker run --rm \
  --env-file .env \
  -e SSH_PASSWORD='change-me' \
  -p 8000:8000 \
  -p 2222:22 \
  qiankun:local
```

连接 SSH:

```bash
ssh root@127.0.0.1 -p 2222
```

容器保留 Xvfb 和 Fluxbox, 供 Camoufox 在虚拟显示器中运行, 不再安装 VNC 或 noVNC。

## cloudflared

默认不启动 cloudflared tunnel:

```text
CLOUDFLARED_TUNNEL_ENABLE=0
```

使用 token tunnel:

```bash
docker run --rm \
  --env-file .env \
  -e SSH_PASSWORD='change-me' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -e CLOUDFLARED_TUNNEL_TOKEN='token' \
  -p 8000:8000 \
  qiankun:local
```

在 Cloudflare Tunnel 的 Public Hostname 中将服务类型设置为 `SSH`, URL 设置为 `localhost:22`。

使用 quick tunnel:

```bash
docker run --rm \
  --env-file .env \
  -e SSH_PASSWORD='change-me' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -e CLOUDFLARED_TUNNEL_URL='ssh://localhost:22' \
  -p 8000:8000 \
  qiankun:local
```

`CLOUDFLARED_TUNNEL_URL` 默认值就是 `ssh://localhost:22`. quick tunnel 会生成公开访问地址, 客户端需通过 cloudflared 建立 SSH 连接。

## 健康检查

镜像内置健康检查:

```text
GET http://127.0.0.1:${PORT}/api/health
```

`PORT` 默认是 `8000`。

## 构建参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `TARGETARCH` | 自动检测 | cloudflared 架构, 支持 `amd64` 和 `arm64` |

## 运行参数

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SSH_PASSWORD` | `12345678` | `root` 用户密码, 生产环境必须修改 |
| `CLOUDFLARED_TUNNEL_ENABLE` | `0` | 设置为 `1` 时启动 cloudflared tunnel |
| `CLOUDFLARED_TUNNEL_URL` | `ssh://localhost:22` | quick tunnel 转发目标 |
