const TOKEN_KEY = "qiankun.token";
const THEME_KEY = "qiankun.theme";

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
