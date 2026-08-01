import type { User } from "@/types";

const TOKEN_KEY = "qiankun.token";
const TOKEN_EXPIRES_AT_KEY = "qiankun.token_expires_at";
const USER_KEY = "qiankun.user";
const THEME_KEY = "qiankun.theme";

/**
 * 主题 key, 供首屏脚本与运行时共用。
 */
export const THEME_STORAGE_KEY = THEME_KEY;

/**
 * 登录会话持久化载荷。
 */
export interface SessionSnapshot {
  /**
   * 访问令牌。
   */
  token: string;
  /**
   * 过期时间戳 (毫秒)。
   */
  expiresAt: number;
  /**
   * 当前用户。
   */
  user: User;
}

/**
 * 浏览器本地存储封装。
 */
export const storage = {
  /**
   * 读取访问令牌。
   */
  getToken(): string | null {
    return window.localStorage.getItem(TOKEN_KEY);
  },

  /**
   * 保存访问令牌。
   */
  setToken(token: string): void {
    window.localStorage.setItem(TOKEN_KEY, token);
  },

  /**
   * 移除访问令牌。
   */
  removeToken(): void {
    window.localStorage.removeItem(TOKEN_KEY);
  },

  /**
   * 读取令牌过期时间戳 (毫秒)。
   */
  getTokenExpiresAt(): number | null {
    const raw = window.localStorage.getItem(TOKEN_EXPIRES_AT_KEY);
    if (!raw) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  },

  /**
   * 保存令牌过期时间戳 (毫秒)。
   */
  setTokenExpiresAt(expiresAt: number): void {
    window.localStorage.setItem(TOKEN_EXPIRES_AT_KEY, String(expiresAt));
  },

  /**
   * 移除令牌过期时间。
   */
  removeTokenExpiresAt(): void {
    window.localStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
  },

  /**
   * 判断令牌是否已过期。
   */
  isTokenExpired(now = Date.now()): boolean {
    const expiresAt = storage.getTokenExpiresAt();
    if (expiresAt === null) return false;
    return expiresAt <= now;
  },

  /**
   * 读取当前用户。
   */
  getUser(): User | null {
    const raw = window.localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as User;
      if (!parsed || typeof parsed.id !== "number" || typeof parsed.username !== "string") return null;
      return parsed;
    } catch {
      return null;
    }
  },

  /**
   * 保存当前用户。
   */
  setUser(user: User): void {
    window.localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  /**
   * 移除当前用户。
   */
  removeUser(): void {
    window.localStorage.removeItem(USER_KEY);
  },

  /**
   * 写入完整登录会话。
   */
  setSession(snapshot: SessionSnapshot): void {
    storage.setToken(snapshot.token);
    storage.setTokenExpiresAt(snapshot.expiresAt);
    storage.setUser(snapshot.user);
  },

  /**
   * 清理登录会话相关存储。
   */
  clearSession(): void {
    storage.removeToken();
    storage.removeTokenExpiresAt();
    storage.removeUser();
  },

  /**
   * 读取主题配置。
   */
  getTheme(): "light" | "dark" | null {
    const theme = window.localStorage.getItem(THEME_KEY);
    return theme === "dark" || theme === "light" ? theme : null;
  },

  /**
   * 保存主题配置。
   */
  setTheme(theme: "light" | "dark"): void {
    window.localStorage.setItem(THEME_KEY, theme);
  },
};
