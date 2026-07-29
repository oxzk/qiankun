import type { TokenResponse, User } from "@/types";
import { storage, type SessionSnapshot } from "@/lib/storage";

/**
 * 根据登录响应构建会话快照。
 */
export function buildSessionSnapshot(token: TokenResponse, now = Date.now()): SessionSnapshot {
  return {
    token: token.access_token,
    expiresAt: now + Math.max(0, token.expires_in) * 1000,
    user: {
      id: token.user.id,
      username: token.user.username,
    },
  };
}

/**
 * 写入登录会话。
 */
export function persistLoginSession(token: TokenResponse, now = Date.now()): SessionSnapshot {
  const snapshot = buildSessionSnapshot(token, now);
  storage.setSession(snapshot);
  return snapshot;
}

/**
 * 读取本地有效会话; 过期则清理并返回 null。
 */
export function readValidLocalSession(now = Date.now()): { token: string; user: User | null; expiresAt: number | null } | null {
  const token = storage.getToken();
  if (!token) return null;
  if (storage.isTokenExpired(now)) {
    storage.clearSession();
    return null;
  }
  return {
    token,
    user: storage.getUser(),
    expiresAt: storage.getTokenExpiresAt(),
  };
}

/**
 * 计算距离过期的剩余毫秒; 未知过期时间返回 null。
 */
export function getTokenRemainingMs(now = Date.now()): number | null {
  const expiresAt = storage.getTokenExpiresAt();
  if (expiresAt === null) return null;
  return expiresAt - now;
}
