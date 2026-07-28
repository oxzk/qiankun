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
| `15902` | noVNC Web 入口 |
| `5900` | 容器内部 VNC 端口, 默认不声明 `EXPOSE` |

## 运行 noVNC

只发布 noVNC Web 入口:

```bash
docker run --rm \
  --env-file .env \
  -e VNC_PASSWORD='change-me' \
  -p 8000:8000 \
  -p 15902:15902 \
  qiankun:local
```

访问:

```text
http://127.0.0.1:15902/
```

建议始终设置 `VNC_PASSWORD`。未设置时, 入口脚本会保留无密码 VNC 以兼容本地开发, 但会输出警告。

## cloudflared

默认不启动 cloudflared tunnel:

```text
CLOUDFLARED_TUNNEL_ENABLE=0
```

使用 token tunnel:

```bash
docker run --rm \
  --env-file .env \
  -e VNC_PASSWORD='change-me' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -e CLOUDFLARED_TUNNEL_TOKEN='token' \
  -p 8000:8000 \
  qiankun:local
```

使用 quick tunnel:

```bash
docker run --rm \
  --env-file .env \
  -e VNC_PASSWORD='change-me' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -e CLOUDFLARED_TUNNEL_URL='http://127.0.0.1:15902' \
  -p 8000:8000 \
  qiankun:local
```

quick tunnel 会生成公开访问地址, 只应在明确需要远程访问 noVNC 时启用。

## 健康检查

镜像内置健康检查:

```text
GET http://127.0.0.1:${PORT}/api/health
```

`PORT` 默认是 `8000`。

## 构建参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `NOVNC_VERSION` | `1.7.0` | noVNC 版本 |
| `TARGETARCH` | 自动检测 | cloudflared 架构, 支持 `amd64` 和 `arm64` |
