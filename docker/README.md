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

容器保留 Xvfb 和 Fluxbox, 供 Camoufox 在虚拟显示器中运行, 不再安装 VNC 或 noVNC。

## 健康检查

镜像内置健康检查:

```text
GET http://127.0.0.1:${PORT}/api/health
```

`PORT` 默认是 `8000`。
