FROM node:22-slim AS frontend-builder

WORKDIR /build

COPY src/package.json src/package-lock.json ./
RUN npm ci

COPY src ./
RUN npm run build
RUN test -f /build/dist/index.html

FROM oxzk/python

ARG TARGETARCH

WORKDIR /app

ENV DISPLAY=:99 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    DEBIAN_FRONTEND=noninteractive \
    XVFB_WHD=1920x1080x24 \
    SSH_PASSWORD=12345678 \
    PORT=8000 \
    CLOUDFLARED_TUNNEL_ENABLE=0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# 安装 Camoufox 图形运行、OpenSSH Server 与 cloudflared 所需的系统依赖。
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        dbus \
        fluxbox \
        fonts-noto-cjk \
        libasound2 \
        libgtk-3-0 \
        libx11-xcb1 \
        openssh-server \
        procps \
        xvfb; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE /app/

# 安装 cloudflared。
RUN set -eux; \
    build_arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "${build_arch}" in \
        amd64) cloudflared_arch="amd64" ;; \
        arm64) cloudflared_arch="arm64" ;; \
        *) echo "不支持的架构: ${build_arch}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cloudflared_arch}" \
        -o /usr/local/bin/cloudflared; \
    chmod +x /usr/local/bin/cloudflared

RUN mkdir -p /app/user_data

COPY app /app/app
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
COPY --from=frontend-builder /build/dist /app/public
RUN test -f /app/public/index.html

# 安装项目依赖、Camoufox 依赖与浏览器文件。
RUN --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential; \
    uv sync --frozen --no-dev --no-editable; \
    apt-get purge -y --auto-remove build-essential; \
    rm -rf /var/lib/apt/lists/*; \
    python -m camoufox fetch

COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 22 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\""]
