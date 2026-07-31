FROM node:22-slim AS frontend-builder

WORKDIR /build

COPY src/package.json src/package-lock.json ./
RUN npm ci

COPY src ./
RUN npm run build
RUN test -f /build/dist/index.html

FROM oxzk/python

WORKDIR /workspace

ENV DISPLAY=:99 \
    VIRTUAL_ENV=/workspace/.venv \
    PATH="/workspace/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    DEBIAN_FRONTEND=noninteractive \
    XVFB_WHD=1920x1080x24 \
    PORT=8000

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# 安装 Camoufox 图形运行所需的系统依赖。
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
        xvfb; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE /workspace/

COPY app /workspace/app
COPY migrations /workspace/migrations
COPY alembic.ini /workspace/alembic.ini
COPY --from=frontend-builder /build/dist /workspace/public
RUN test -f /workspace/public/index.html

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

ENTRYPOINT ["/entrypoint.sh"]
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT}\""]
