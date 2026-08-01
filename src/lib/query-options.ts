/**
 * 资源缓存时效档位 (毫秒)。
 */
export const queryStaleTime = {
  /**
   * 运行态数据。
   */
  realtime: 3_000,
  /**
   * 常规列表。
   */
  list: 10_000,
  /**
   * 统计摘要。
   */
  stats: 15_000,
  /**
   * 目录类低频数据。
   */
  catalog: 60_000,
} as const;

/**
 * 运行中任务轮询间隔 (毫秒)。
 */
export const RUNNING_POLL_INTERVAL_MS = 3_000;

/**
 * 令牌过期前提前提醒窗口 (毫秒)。
 */
export const TOKEN_EXPIRY_WARN_MS = 60_000;
