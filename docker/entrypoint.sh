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

# 等待端口监听, 避免固定 sleep 在慢机器上误判服务状态。
wait_for_port() {
    local name="$1"
    local port="$2"
    local timeout="${3:-30}"

    for i in $(seq 1 "${timeout}"); do
        if (echo >"/dev/tcp/127.0.0.1/${port}") >/dev/null 2>&1; then
            log "${name} 已监听端口 ${port}"
            return 0
        fi

        log "等待 ${name} 启动中... (${i}/${timeout})"
        sleep 1
    done

    log "警告: ${name} 未在 ${timeout} 秒内监听端口 ${port}"
    return 1
}

# 从 cloudflared 日志解析 quick tunnel 访问地址, 最多等待指定秒数。
wait_for_cloudflared_url() {
    local log_file="$1"
    local timeout="${2:-60}"
    local tunnel_url=""

    for i in $(seq 1 "${timeout}"); do
        tunnel_url="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' "${log_file}" 2>/dev/null | tail -n 1 || true)"
        if [[ -n "${tunnel_url}" ]]; then
            log "cloudflared 访问地址: ${tunnel_url}"
            return 0
        fi

        if ! pgrep -x cloudflared >/dev/null; then
            log "警告: cloudflared 已退出, 未解析到访问地址"
            return 1
        fi

        log "等待 cloudflared 访问地址... (${i}/${timeout})"
        sleep 1
    done

    log "警告: ${timeout} 秒内未解析到 cloudflared 访问地址, 请查看 ${log_file}"
    return 1
}

# 配置基础环境。
export DISPLAY="${DISPLAY:-:99}"
export XVFB_WHD="${XVFB_WHD:-1920x1080x24}"
export SSH_PASSWORD="${SSH_PASSWORD:-12345678}"
export SSH_PORT="${SSH_PORT:-22}"
export CLOUDFLARED_TUNNEL_ENABLE="${CLOUDFLARED_TUNNEL_ENABLE:-0}"
export CLOUDFLARED_TUNNEL_URL="${CLOUDFLARED_TUNNEL_URL:-ssh://localhost:${SSH_PORT}}"

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

if [[ -z "${SSH_PASSWORD}" ]]; then
    log "错误: SSH_PASSWORD 不能为空"
    exit 1
fi

printf 'root:%s\n' "${SSH_PASSWORD}" | chpasswd
install -d -m 0755 /run/sshd
ssh-keygen -A >/tmp/ssh-keygen.log 2>&1

# 使用启动参数约束 SSH 登录能力, 避免依赖额外配置文件。
SSH_CONFIG_ARGS=(
    -o "PermitRootLogin=yes"
    -o "PasswordAuthentication=yes"
    -o "KbdInteractiveAuthentication=no"
    -o "AllowUsers=root"
    -o "X11Forwarding=no"
    -o "AllowAgentForwarding=no"
    -o "AllowTcpForwarding=no"
    -o "PermitTunnel=no"
)

start_background "OpenSSH Server: ${SSH_PORT}" /tmp/sshd.log \
    /usr/sbin/sshd -D -e -p "${SSH_PORT}" "${SSH_CONFIG_ARGS[@]}"
wait_for_port "OpenSSH Server" "${SSH_PORT}" 30

if [[ "${CLOUDFLARED_TUNNEL_ENABLE}" == "1" ]]; then
    if [[ -n "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]]; then
        start_background "cloudflared token tunnel" /tmp/cloudflared.log \
            cloudflared tunnel --no-autoupdate run --token "${CLOUDFLARED_TUNNEL_TOKEN}"
    else
        start_background "cloudflared quick tunnel: ${CLOUDFLARED_TUNNEL_URL}" /tmp/cloudflared.log \
            cloudflared tunnel --no-autoupdate --url "${CLOUDFLARED_TUNNEL_URL}"
        wait_for_cloudflared_url /tmp/cloudflared.log 60 || true
    fi
fi

if [[ $# -eq 0 ]]; then
    log "未提供自定义命令, 容器将保持运行"
    touch /tmp/xvfb.log /tmp/fluxbox.log /tmp/sshd.log /tmp/cloudflared.log
    tail -f /tmp/xvfb.log /tmp/fluxbox.log /tmp/sshd.log /tmp/cloudflared.log
fi

log "OpenSSH Server 已就绪: root@127.0.0.1:${SSH_PORT}"
log "执行自定义命令: $*"
"$@" &
MAIN_PID="$!"
wait "${MAIN_PID}"
