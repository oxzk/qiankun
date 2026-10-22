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
  -p 15902:15902 \
  -p 5900:5900 \
  qiankun:local
```

默认端口:

| 端口 | 说明 |
| --- | --- |
| `8000` | API 和前端静态页面 |
| `5900` | VNC 客户端连接端口 |
| `15902` | noVNC Web 访问端口 |

浏览器访问 `http://127.0.0.1:15902/` 即可进入 noVNC. 建议通过 `VNC_PASSWORD` 设置 VNC 密码; 未设置时仅适合不发布 VNC 与 noVNC 端口的可信环境.

## Cloudflare Tunnel

临时 quick tunnel 默认代理 noVNC, 启动后从容器日志获取 `trycloudflare.com` 地址:

```bash
docker run --rm \
  --env-file .env \
  -e VNC_PASSWORD='replace-with-a-strong-password' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -p 8000:8000 \
  qiankun:local
```

使用已创建的 Cloudflare Tunnel token:

```bash
docker run --rm \
  --env-file .env \
  -e VNC_PASSWORD='replace-with-a-strong-password' \
  -e CLOUDFLARED_TUNNEL_ENABLE=1 \
  -e CLOUDFLARED_TUNNEL_TOKEN='<tunnel-token>' \
  -p 8000:8000 \
  qiankun:local
```

可用环境变量:

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VNC_PASSWORD` | 空 | VNC 与 noVNC 密码; 开启 Cloudflare Tunnel 时必填 |
| `VNC_PORT` | `5900` | VNC 监听端口 |
| `NOVNC_PORT` | `15902` | noVNC 监听端口 |
| `CLOUDFLARED_TUNNEL_ENABLE` | `0` | 设置为 `1` 时启动 Cloudflare Tunnel |
| `CLOUDFLARED_TUNNEL_URL` | `http://127.0.0.1:15902` | quick tunnel 代理目标 |
| `CLOUDFLARED_TUNNEL_TOKEN` | 空 | 已创建的 Tunnel token; 留空时创建 quick tunnel |

## 健康检查

镜像内置健康检查:

```text
GET http://127.0.0.1:${PORT}/api/health
```

`PORT` 默认是 `8000`。
