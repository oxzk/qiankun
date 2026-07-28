/**
 * React Query 缓存键。
 */
export const queryKeys = {
  stats: {
    taskStats: ["task-stats"] as const,
  },
  tasks: {
    root: ["tasks"] as const,
    list: (params: unknown) => ["tasks", params] as const,
    dashboard: ["tasks", "dashboard"] as const,
  },
  executions: {
    root: ["executions"] as const,
    list: (params: unknown) => ["executions", params] as const,
    detail: (id: number) => ["executions", "detail", id] as const,
    running: ["executions", "running"] as const,
    dashboard: ["executions", "dashboard"] as const,
  },
  providers: {
    root: ["providers"] as const,
    list: (params: unknown) => ["providers", params] as const,
  },
  notifications: {
    root: ["notifications"] as const,
  },
  backups: {
    root: ["backups"] as const,
  },
};
