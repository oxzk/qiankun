import type { ExecutionStatus } from "@/types";

/**
 * 任务列表缓存参数。
 */
export interface TasksListKeyParams {
  /**
   * 页码。
   */
  page: number;
  /**
   * 名称筛选。
   */
  name: string;
  /**
   * 启用状态筛选。
   */
  enabled: boolean | "";
}

/**
 * 执行记录列表缓存参数。
 */
export interface ExecutionsListKeyParams {
  /**
   * 页码。
   */
  page: number;
  /**
   * 任务 ID 筛选。
   */
  taskId: string;
  /**
   * 任务名称筛选。
   */
  taskName: string;
  /**
   * 状态筛选。
   */
  status: ExecutionStatus | "";
}

/**
 * Provider 列表缓存参数。
 */
export interface ProvidersListKeyParams {
  /**
   * 页码。
   */
  page: number;
}

/**
 * React Query 缓存键。
 */
export const queryKeys = {
  stats: {
    taskStats: ["task-stats"] as const,
  },
  auth: {
    me: ["auth", "me"] as const,
  },
  tasks: {
    root: ["tasks"] as const,
    list: (params: TasksListKeyParams) => ["tasks", "list", params] as const,
    dashboard: ["tasks", "dashboard"] as const,
  },
  executions: {
    root: ["executions"] as const,
    list: (params: ExecutionsListKeyParams) => ["executions", "list", params] as const,
    detail: (id: number) => ["executions", "detail", id] as const,
    running: ["executions", "running"] as const,
    dashboard: ["executions", "dashboard"] as const,
  },
  providers: {
    root: ["providers"] as const,
    list: (params: ProvidersListKeyParams) => ["providers", "list", params] as const,
    options: ["providers", "options"] as const,
  },
  notifications: {
    root: ["notifications"] as const,
    options: ["notifications", "options"] as const,
  },
  backups: {
    root: ["backups"] as const,
  },
};
