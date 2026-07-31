#!/usr/bin/env bash
set -Eeuo pipefail

BACKGROUND_PIDS=()
MAIN_PID=""

# 统一日志输出, 便于在容器日志中快速定位启动阶段.
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# 清理后台进程, 避免容器退出后残留子进程.
cleanup() {
    local exit_code=$?

    if [[ -n "${MAIN_PID}" ]]; then
        kill "${MAIN_PID}" >/dev/null 2>&1 || true
    fi

    if [[ "${#BACKGROUND_PIDS[@]}" -gt 0 ]]; then
        log "清理后台进程"
        kill "${BACKGROUND_PIDS[@]}" >/dev/null 2>&1 || true
        wait "${BACKGROUND_PIDS[@]}" >/dev/null 2>&1 || true
    fi

    rm -f /tmp/x11vnc.pass

    exit "${exit_code}"
}

# 转发终止信号给主进程, 再交给 cleanup 统一清理.
terminate() {
    if [[ -n "${MAIN_PID}" ]]; then
        kill -TERM "${MAIN_PID}" >/dev/null 2>&1 || true
    fi
    exit 143
}

trap cleanup EXIT
trap terminate TERM INT

# 启动后台进程并记录 PID.
start_background() {
    local name="$1"
    local log_file="$2"
    shift 2

    log "启动 ${name}"
    "$@" >"${log_file}" 2>&1 &
    BACKGROUND_PIDS+=("$!")
}

# 等待端口监听, 确保依赖服务已经就绪.
wait_for_port() {
    local name="$1"
    local port="$2"
    local timeout="${3:-30}"

    for ((attempt = 1; attempt <= timeout; attempt++)); do
        if (echo >"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1; then
            log "${name} 已监听端口 ${port}"
            return 0
        fi

        sleep 1
    done

    log "错误: ${name} 未在 ${timeout} 秒内监听端口 ${port}"
    return 1
}

# 从 cloudflared 日志解析 quick tunnel 访问地址.
wait_for_cloudflared_url() {
    local log_file="$1"
    local cloudflared_pid="$2"
    local timeout="${3:-60}"
    local tunnel_url=""

    for ((attempt = 1; attempt <= timeout; attempt++)); do
        tunnel_url="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "${log_file}" 2>/dev/null | tail -n 1 || true)"
        if [[ -n "${tunnel_url}" ]]; then
            log "cloudflared 访问地址: ${tunnel_url}"
            return 0
        fi

        if ! kill -0 "${cloudflared_pid}" >/dev/null 2>&1; then
            log "错误: cloudflared 已退出, 详细信息见 ${log_file}"
            return 1
        fi

        sleep 1
    done

    log "错误: ${timeout} 秒内未解析到 cloudflared 访问地址, 详细信息见 ${log_file}"
    return 1
}

# 配置基础环境.
export DISPLAY="${DISPLAY:-:99}"
export XVFB_WHD="${XVFB_WHD:-1920x1080x24}"
export VNC_PORT="${VNC_PORT:-5900}"
export NOVNC_PORT="${NOVNC_PORT:-15902}"
export CLOUDFLARED_TUNNEL_ENABLE="${CLOUDFLARED_TUNNEL_ENABLE:-0}"
export CLOUDFLARED_TUNNEL_URL="${CLOUDFLARED_TUNNEL_URL:-http://127.0.0.1:${NOVNC_PORT}}"

rm -f "/tmp/.X${DISPLAY#:}-lock"

# Chromium/Firefox 相关库会尝试访问 D-Bus, 启动失败不影响主流程.
mkdir -p /run/dbus /var/run/dbus
rm -f /run/dbus/pid /var/run/dbus/pid
dbus-uuidgen --ensure 2>/dev/null || true
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/dbus/session_bus_socket"
dbus-daemon --session --fork --address="${DBUS_SESSION_BUS_ADDRESS}" --print-address >/tmp/dbus.log 2>&1 || true

start_background "Xvfb: ${DISPLAY} (${XVFB_WHD})" /tmp/xvfb.log \
    Xvfb "${DISPLAY}" -screen 0 "${XVFB_WHD}" -ac -nolisten tcp +extension GLX +extension RANDR +render -noreset
sleep 1

start_background "Fluxbox" /tmp/fluxbox.log fluxbox
sleep 1

VNC_AUTH_ARGS=("-nopw")
if [[ -n "${VNC_PASSWORD:-}" ]]; then
    x11vnc -storepasswd "${VNC_PASSWORD}" /tmp/x11vnc.pass >/tmp/x11vnc-pass.log 2>&1
    VNC_AUTH_ARGS=("-rfbauth" "/tmp/x11vnc.pass")
    log "已启用 VNC 密码认证"
else
    log "警告: 未设置 VNC_PASSWORD, VNC 将使用无密码认证"
fi

start_background "x11vnc: ${VNC_PORT}" /tmp/x11vnc.log \
    x11vnc -display "${DISPLAY}" -forever "${VNC_AUTH_ARGS[@]}" -rfbport "${VNC_PORT}" -shared
wait_for_port "x11vnc" "${VNC_PORT}"

log "创建 noVNC 自适应入口页"
cat > /opt/noVNC/index.html <<'NOVNC_HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>QianKun noVNC</title>
  <style>
    html, body, iframe { width: 100%; height: 100%; }
    body { margin: 0; overflow: hidden; background: #000; }
    iframe { border: 0; }
  </style>
</head>
<body>
  <iframe src="vnc.html?autoconnect=true&resize=scale&quality=6" title="QianKun noVNC"></iframe>
</body>
</html>
NOVNC_HTML

start_background "noVNC: ${NOVNC_PORT}" /tmp/novnc.log \
    websockify --web /opt/noVNC "${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}"
wait_for_port "noVNC" "${NOVNC_PORT}"

if [[ "${CLOUDFLARED_TUNNEL_ENABLE}" == "1" ]]; then
    if [[ -z "${VNC_PASSWORD:-}" ]]; then
        log "错误: 开启 Cloudflare Tunnel 时必须设置 VNC_PASSWORD"
        exit 1
    fi

    if [[ -n "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]]; then
        start_background "cloudflared token tunnel" /tmp/cloudflared.log \
            cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARED_TUNNEL_TOKEN}"
        sleep 2
        if ! kill -0 "${BACKGROUND_PIDS[-1]}" >/dev/null 2>&1; then
            log "错误: cloudflared 已退出, 详细信息见 /tmp/cloudflared.log"
            exit 1
        fi
    else
        start_background "cloudflared quick tunnel: ${CLOUDFLARED_TUNNEL_URL}" /tmp/cloudflared.log \
            cloudflared tunnel --no-autoupdate --url "${CLOUDFLARED_TUNNEL_URL}"
        wait_for_cloudflared_url /tmp/cloudflared.log "${BACKGROUND_PIDS[-1]}" 60
    fi
fi

if [[ $# -eq 0 ]]; then
    log "未提供自定义命令, 容器将保持运行"
    touch /tmp/xvfb.log /tmp/fluxbox.log /tmp/x11vnc.log /tmp/novnc.log /tmp/cloudflared.log
    tail -f /tmp/xvfb.log /tmp/fluxbox.log /tmp/x11vnc.log /tmp/novnc.log /tmp/cloudflared.log &
    MAIN_PID="$!"
    wait "${MAIN_PID}"
    exit 0
fi

log "noVNC 已就绪: http://127.0.0.1:${NOVNC_PORT}/"
log "执行自定义命令: $*"
"$@" &
MAIN_PID="$!"
wait "${MAIN_PID}"
