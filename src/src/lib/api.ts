import { API_PREFIX, compactParams, http, unwrap, withSignal } from "@/lib/http";
import type {
  BackupInfo,
  Execution,
  ExecutionStatus,
  JsonRecord,
  NotificationPayload,
  NotificationSetting,
  PaginatedResponse,
  ProviderInfo,
  ProviderPayload,
  ProviderResult,
  ProviderValidateResult,
  Task,
  TaskPayload,
  TaskStats,
  TokenResponse,
  User,
} from "@/types";

export { getErrorMessage } from "@/lib/http";

/**
 * 列表查询公共分页参数。
 */
export interface PageQuery {
  /**
   * 页码。
   */
  page?: number;
  /**
   * 每页条数。
   */
  page_size?: number;
}

/**
 * 任务列表查询参数。
 */
export interface TasksListQuery extends PageQuery {
  /**
   * 启用状态筛选。
   */
  enabled?: boolean | "";
  /**
   * 执行器名称筛选。
   */
  provider_name?: string;
  /**
   * 任务名称筛选。
   */
  name?: string;
}

/**
 * 执行记录列表查询参数。
 */
export interface ExecutionsListQuery extends PageQuery {
  /**
   * 任务 ID 筛选。
   */
  task_id?: number | "";
  /**
   * 任务名称筛选。
   */
  task_name?: string;
  /**
   * 执行状态筛选。
   */
  status?: ExecutionStatus | "";
}

/**
 * Provider 列表查询参数。
 */
export interface ProvidersListQuery extends PageQuery {
  /**
   * 启用状态筛选。
   */
  enabled?: boolean | "";
}

/**
 * 认证接口。
 */
export const authApi = {
  /**
   * 用户名密码登录。
   */
  login(username: string, password: string, signal?: AbortSignal): Promise<TokenResponse> {
    return unwrap<TokenResponse>(
      http.post(`${API_PREFIX}/auth/login`, { username, password }, withSignal(signal)),
    );
  },

  /**
   * 查询当前登录用户。
   */
  me(signal?: AbortSignal): Promise<User> {
    return unwrap<User>(http.get(`${API_PREFIX}/auth/me`, withSignal(signal)));
  },

  /**
   * 修改密码。
   */
  changePassword(old_password: string, new_password: string, signal?: AbortSignal): Promise<boolean> {
    return unwrap<boolean>(
      http.post(`${API_PREFIX}/auth/change-password`, { old_password, new_password }, withSignal(signal)),
    );
  },
};

/**
 * 统计接口。
 */
export const statsApi = {
  /**
   * 查询任务统计摘要。
   */
  getStats(signal?: AbortSignal): Promise<TaskStats> {
    return unwrap<TaskStats>(http.get(`${API_PREFIX}/stats`, withSignal(signal)));
  },
};

/**
 * 任务接口。
 */
export const tasksApi = {
  /**
   * 分页查询任务。
   */
  list(query: TasksListQuery = {}, signal?: AbortSignal): Promise<PaginatedResponse<Task>> {
    return unwrap<PaginatedResponse<Task>>(
      http.get(`${API_PREFIX}/tasks`, { params: compactParams(query), ...withSignal(signal) }),
    );
  },
  /**
   * 创建任务。
   */
  create(payload: TaskPayload, signal?: AbortSignal): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks`, payload, withSignal(signal)));
  },
  /**
   * 更新任务。
   */
  update(taskId: number, payload: TaskPayload, signal?: AbortSignal): Promise<Task> {
    return unwrap<Task>(http.put(`${API_PREFIX}/tasks/${taskId}`, payload, withSignal(signal)));
  },
  /**
   * 删除任务。
   */
  delete(taskId: number, signal?: AbortSignal): Promise<null> {
    return unwrap<null>(http.delete(`${API_PREFIX}/tasks/${taskId}`, withSignal(signal)));
  },
  /**
   * 手动触发任务。
   */
  run(taskId: number, signal?: AbortSignal): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/tasks/${taskId}/run`, undefined, withSignal(signal)));
  },
  /**
   * 取消任务当前执行。
   */
  cancel(taskId: number, signal?: AbortSignal): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/tasks/${taskId}/cancel`, undefined, withSignal(signal)));
  },
  /**
   * 启用任务。
   */
  enable(taskId: number, signal?: AbortSignal): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks/${taskId}/enable`, undefined, withSignal(signal)));
  },
  /**
   * 停用任务。
   */
  disable(taskId: number, signal?: AbortSignal): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks/${taskId}/disable`, undefined, withSignal(signal)));
  },
};

/**
 * 执行记录接口。
 */
export const executionsApi = {
  /**
   * 分页查询执行记录。
   */
  list(query: ExecutionsListQuery = {}, signal?: AbortSignal): Promise<PaginatedResponse<Execution>> {
    return unwrap<PaginatedResponse<Execution>>(
      http.get(`${API_PREFIX}/executions`, { params: compactParams(query), ...withSignal(signal) }),
    );
  },
  /**
   * 查询执行详情。
   */
  get(executionId: number, signal?: AbortSignal): Promise<Execution> {
    return unwrap<Execution>(http.get(`${API_PREFIX}/executions/${executionId}`, withSignal(signal)));
  },
  /**
   * 删除执行记录。
   */
  delete(executionId: number, signal?: AbortSignal): Promise<null> {
    return unwrap<null>(http.delete(`${API_PREFIX}/executions/${executionId}`, withSignal(signal)));
  },
};

/**
 * Provider 接口。
 */
export const providersApi = {
  /**
   * 分页查询执行器。
   */
  list(query: ProvidersListQuery = {}, signal?: AbortSignal): Promise<PaginatedResponse<ProviderInfo>> {
    return unwrap<PaginatedResponse<ProviderInfo>>(
      http.get(`${API_PREFIX}/providers`, { params: compactParams(query), ...withSignal(signal) }),
    );
  },
  /**
   * 查询单个执行器。
   */
  get(providerName: string, signal?: AbortSignal): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(
      http.get(`${API_PREFIX}/providers/${encodeURIComponent(providerName)}`, withSignal(signal)),
    );
  },
  /**
   * 创建执行器。
   */
  create(payload: ProviderPayload, signal?: AbortSignal): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.post(`${API_PREFIX}/providers`, payload, withSignal(signal)));
  },
  /**
   * 更新执行器。
   */
  update(providerName: string, payload: ProviderPayload, signal?: AbortSignal): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(
      http.put(`${API_PREFIX}/providers/${encodeURIComponent(providerName)}`, payload, withSignal(signal)),
    );
  },
  /**
   * 启用执行器。
   */
  enable(providerName: string, signal?: AbortSignal): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(
      http.post(`${API_PREFIX}/providers/${encodeURIComponent(providerName)}/enable`, undefined, withSignal(signal)),
    );
  },
  /**
   * 停用执行器。
   */
  disable(providerName: string, signal?: AbortSignal): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(
      http.post(`${API_PREFIX}/providers/${encodeURIComponent(providerName)}/disable`, undefined, withSignal(signal)),
    );
  },
  /**
   * 读取执行器默认配置。
   */
  config(providerName: string, signal?: AbortSignal): Promise<JsonRecord> {
    return unwrap<JsonRecord>(
      http.get(`${API_PREFIX}/providers/${encodeURIComponent(providerName)}/config`, withSignal(signal)),
    );
  },
  /**
   * 同步内置执行器。
   */
  sync(signal?: AbortSignal): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/providers/sync`, undefined, withSignal(signal)));
  },
  /**
   * 校验执行器配置。
   */
  validateConfig(providerName: string, config: JsonRecord, signal?: AbortSignal): Promise<ProviderValidateResult> {
    return unwrap<ProviderValidateResult>(
      http.post(
        `${API_PREFIX}/providers/${encodeURIComponent(providerName)}/validate-config`,
        { config },
        withSignal(signal),
      ),
    );
  },
  /**
   * 测试运行执行器。
   */
  testRun(providerName: string, config: JsonRecord = {}, signal?: AbortSignal): Promise<ProviderResult> {
    return unwrap<ProviderResult>(
      http.post(
        `${API_PREFIX}/providers/${encodeURIComponent(providerName)}/test-run`,
        { config },
        withSignal(signal),
      ),
    );
  },
};

/**
 * 数据备份接口。
 */
export const backupsApi = {
  /**
   * 列出备份。
   */
  list(signal?: AbortSignal): Promise<BackupInfo[]> {
    return unwrap<BackupInfo[]>(http.get(`${API_PREFIX}/backups`, withSignal(signal)));
  },
  /**
   * 创建备份。
   */
  create(signal?: AbortSignal): Promise<BackupInfo> {
    return unwrap<BackupInfo>(http.post(`${API_PREFIX}/backups`, undefined, withSignal(signal)));
  },
  /**
   * 恢复备份。
   */
  restore(filename: string, signal?: AbortSignal): Promise<boolean> {
    return unwrap<boolean>(
      http.post(`${API_PREFIX}/backups/${encodeURIComponent(filename)}/restore`, undefined, withSignal(signal)),
    );
  },
};

/**
 * 通知接口。
 */
export const notificationsApi = {
  /**
   * 分页查询通知配置。
   */
  list(query: PageQuery = {}, signal?: AbortSignal): Promise<PaginatedResponse<NotificationSetting>> {
    return unwrap<PaginatedResponse<NotificationSetting>>(
      http.get(`${API_PREFIX}/notifications`, { params: compactParams(query), ...withSignal(signal) }),
    );
  },
  /**
   * 创建通知配置。
   */
  create(payload: NotificationPayload, signal?: AbortSignal): Promise<NotificationSetting> {
    return unwrap<NotificationSetting>(http.post(`${API_PREFIX}/notifications`, payload, withSignal(signal)));
  },
  /**
   * 更新通知配置。
   */
  update(id: number, payload: NotificationPayload, signal?: AbortSignal): Promise<NotificationSetting> {
    return unwrap<NotificationSetting>(http.put(`${API_PREFIX}/notifications/${id}`, payload, withSignal(signal)));
  },
  /**
   * 删除通知配置。
   */
  delete(id: number, signal?: AbortSignal): Promise<null> {
    return unwrap<null>(http.delete(`${API_PREFIX}/notifications/${id}`, withSignal(signal)));
  },
  /**
   * 测试通知渠道。
   */
  test(id: number, message: string, signal?: AbortSignal): Promise<null> {
    return unwrap<null>(http.post(`${API_PREFIX}/notifications/${id}/test`, { message }, withSignal(signal)));
  },
};
