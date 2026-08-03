FROM node:22-slim AS frontend-builder

WORKDIR /build

COPY web/src/package.json web/src/package-lock.json ./
RUN npm ci

COPY public /public
COPY web/src ./
RUN npm run build
RUN test -f /build/dist/index.html

FROM oxzk/python

ARG TARGETARCH
ARG NOVNC_VERSION=1.7.0
ARG WEBSOCKIFY_VERSION=0.13.0

WORKDIR /workspace

ENV XVFB_DISPLAY=:99 \
    DISPLAY=:99 \
    VIRTUAL_ENV=/workspace/.venv \
    PATH="/workspace/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    DEBIAN_FRONTEND=noninteractive \
    XVFB_WHD=1920x1080x24 \
    VNC_PORT=5900 \
    NOVNC_PORT=15902 \
    CLOUDFLARED_TUNNEL_ENABLE=0 \
    CLOUDFLARED_TUNNEL_URL=http://127.0.0.1:15902 \
    PORT=8000

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# 安装 Camoufox 图形运行, VNC 与入口脚本所需的系统依赖.
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
        procps \
        x11vnc \
        xauth \
        xvfb; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE /workspace/

COPY app /workspace/app
COPY migrations /workspace/migrations
COPY alembic.ini /workspace/alembic.ini
COPY --from=frontend-builder /build/dist /workspace/public
RUN test -f /workspace/public/index.html

# 安装项目依赖, websockify, Camoufox 依赖与浏览器文件.
RUN --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends build-essential; \
    uv sync --frozen --no-dev --no-editable; \
    uv pip install --python "${VIRTUAL_ENV}/bin/python" "websockify==${WEBSOCKIFY_VERSION}"; \
    apt-get purge -y --auto-remove build-essential; \
    rm -rf /var/lib/apt/lists/*; \
    python -m camoufox fetch

# 安装 noVNC 与 cloudflared.
RUN set -eux; \
    mkdir -p /opt/noVNC; \
    curl -fsSL "https://github.com/novnc/noVNC/archive/refs/tags/v${NOVNC_VERSION}.tar.gz" \
        | tar -xz --strip-components=1 -C /opt/noVNC; \
    build_arch="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "${build_arch}" in \
        amd64) cloudflared_arch="amd64" ;; \
        arm64) cloudflared_arch="arm64" ;; \
        *) echo "不支持的架构: ${build_arch}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${cloudflared_arch}" \
        -o /usr/local/bin/cloudflared; \
    chmod +x /usr/local/bin/cloudflared

COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 8000 5900 15902

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\""]
