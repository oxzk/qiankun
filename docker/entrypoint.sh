#!/usr/bin/env bash
set -Eeuo pipefail

BACKGROUND_PIDS=()
MAIN_PID=""

# 统一日志输出, 便于在容器日志中快速定位启动阶段。
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# 清理后台进程, 避免容器退出后残留子进程。
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

    exit "${exit_code}"
}

# 转发终止信号给主进程, 再交给 cleanup 统一清理。
terminate() {
    if [[ -n "${MAIN_PID}" ]]; then
        kill -TERM "${MAIN_PID}" >/dev/null 2>&1 || true
    fi
    exit 143
}

trap cleanup EXIT
trap terminate TERM INT

# 启动后台进程并记录 PID。
start_background() {
    local name="$1"
    local log_file="$2"
    shift 2

    log "启动 ${name}"
    "$@" >"${log_file}" 2>&1 &
    BACKGROUND_PIDS+=("$!")
}

# 配置基础环境。
export DISPLAY="${DISPLAY:-:99}"
export XVFB_WHD="${XVFB_WHD:-1920x1080x24}"

rm -f "/tmp/.X${DISPLAY#:}-lock"

# Chromium/Firefox 相关库会尝试访问 D-Bus, 启动失败不影响主流程。
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

if [[ $# -eq 0 ]]; then
    log "未提供自定义命令, 容器将保持运行"
    touch /tmp/xvfb.log /tmp/fluxbox.log
    tail -f /tmp/xvfb.log /tmp/fluxbox.log
fi

log "执行自定义命令: $*"
"$@" &
MAIN_PID="$!"
wait "${MAIN_PID}"
