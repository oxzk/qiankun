import axios, { AxiosError, type AxiosInstance } from "axios";
import { storage } from "@/lib/storage";
import type {
  ApiResponse,
  BackupInfo,
  Execution,
  ExecutionStatus,
  NotificationPayload,
  NotificationSetting,
  PaginatedResponse,
  Task,
  TaskPayload,
  TaskStats,
  TokenResponse,
  ProviderInfo,
  ProviderPayload,
  ProviderResult,
  ProviderValidateResult,
  JsonRecord,
} from "@/types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const API_PREFIX = import.meta.env.VITE_API_PREFIX || "/api";

/**
 * 创建 HTTP 客户端。
 */
function createHttpClient(): AxiosInstance {
  const instance = axios.create({
    baseURL: API_BASE_URL,
    timeout: 60000,
  });

  instance.interceptors.request.use((config) => {
    const token = storage.getToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });

  instance.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiResponse<unknown>>) => {
      if (error.response?.status === 401) {
        storage.removeToken();
        window.dispatchEvent(new CustomEvent("qiankun:unauthorized"));
      }
      return Promise.reject(error);
    },
  );

  return instance;
}

const http = createHttpClient();

/**
 * 清理空查询参数。
 */
function compactParams(params: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(params).filter(
      ([, value]) => value !== undefined && value !== null && value !== ""
    )
  );
}

/**
 * 提取统一响应数据。
 */
async function unwrap<T>(request: Promise<{ data: ApiResponse<T> }>): Promise<T> {
  const response = await request;
  if (!response.data.success) throw new Error(response.data.message || "请求失败");
  return response.data.data as T;
}

/**
 * 提取错误消息。
 */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiResponse<unknown>>(error)) {
    return error.response?.data?.message || error.message || "请求失败";
  }
  if (error instanceof Error) return error.message;
  return "请求失败";
}

/**
 * 认证接口。
 */
export const authApi = {
  /**
   * 用户名密码登录。
   */
  login(username: string, password: string): Promise<TokenResponse> {
    return unwrap<TokenResponse>(http.post(`${API_PREFIX}/auth/login`, { username, password }));
  },

  /**
   * 修改密码。
   */
  changePassword(old_password: string, new_password: string): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/auth/change-password`, { old_password, new_password }));
  },
};

/**
 * 统计接口。
 */
export const statsApi = {
  /**
   * 查询任务统计摘要。
   */
  getStats(): Promise<TaskStats> {
    return unwrap<TaskStats>(http.get(`${API_PREFIX}/stats`));
  },
};

/**
 * 任务接口。
 */
export const tasksApi = {
  list(query: {
    page?: number;
    page_size?: number;
    enabled?: boolean | "";
    provider_name?: string;
    name?: string;
  } = {}): Promise<PaginatedResponse<Task>> {
    return unwrap<PaginatedResponse<Task>>(http.get(`${API_PREFIX}/tasks`, { params: compactParams(query) }));
  },
  create(payload: TaskPayload): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks`, payload));
  },
  update(taskId: number, payload: TaskPayload): Promise<Task> {
    return unwrap<Task>(http.put(`${API_PREFIX}/tasks/${taskId}`, payload));
  },
  delete(taskId: number): Promise<null> {
    return unwrap<null>(http.delete(`${API_PREFIX}/tasks/${taskId}`));
  },
  run(taskId: number): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/tasks/${taskId}/run`));
  },
  cancel(taskId: number): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/tasks/${taskId}/cancel`));
  },
  enable(taskId: number): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks/${taskId}/enable`));
  },
  disable(taskId: number): Promise<Task> {
    return unwrap<Task>(http.post(`${API_PREFIX}/tasks/${taskId}/disable`));
  },
};

/**
 * 执行记录接口。
 */
export const executionsApi = {
  list(query: { page?: number; page_size?: number; task_id?: number | ""; task_name?: string; status?: ExecutionStatus | "" } = {}): Promise<PaginatedResponse<Execution>> {
    return unwrap<PaginatedResponse<Execution>>(http.get(`${API_PREFIX}/executions`, { params: compactParams(query) }));
  },
  get(executionId: number): Promise<Execution> {
    return unwrap<Execution>(http.get(`${API_PREFIX}/executions/${executionId}`));
  },
};

/**
 * Provider 接口。
 */
export const providersApi = {
  list(query: { page?: number; page_size?: number; enabled?: boolean | "" } = {}): Promise<PaginatedResponse<ProviderInfo>> {
    return unwrap<PaginatedResponse<ProviderInfo>>(http.get(`${API_PREFIX}/providers`, { params: compactParams(query) }));
  },
  get(providerName: string): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.get(`${API_PREFIX}/providers/${providerName}`));
  },
  create(payload: ProviderPayload): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.post(`${API_PREFIX}/providers`, payload));
  },
  update(providerName: string, payload: ProviderPayload): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.put(`${API_PREFIX}/providers/${providerName}`, payload));
  },
  enable(providerName: string): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.post(`${API_PREFIX}/providers/${providerName}/enable`));
  },
  disable(providerName: string): Promise<ProviderInfo> {
    return unwrap<ProviderInfo>(http.post(`${API_PREFIX}/providers/${providerName}/disable`));
  },
  config(providerName: string): Promise<JsonRecord> {
    return unwrap<JsonRecord>(http.get(`${API_PREFIX}/providers/${providerName}/config`));
  },
  sync(): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/providers/sync`));
  },
  validateConfig(providerName: string, config: JsonRecord): Promise<ProviderValidateResult> {
    return unwrap<ProviderValidateResult>(
      http.post(`${API_PREFIX}/providers/${providerName}/validate-config`, { config })
    );
  },
  testRun(providerName: string, config: JsonRecord = {}): Promise<ProviderResult> {
    return unwrap<ProviderResult>(
      http.post(`${API_PREFIX}/providers/${providerName}/test-run`, { config })
    );
  },
};

/**
 * 数据备份接口。
 */
export const backupsApi = {
  list(): Promise<BackupInfo[]> {
    return unwrap<BackupInfo[]>(http.get(`${API_PREFIX}/backups`));
  },
  create(): Promise<BackupInfo> {
    return unwrap<BackupInfo>(http.post(`${API_PREFIX}/backups`));
  },
  restore(filename: string): Promise<boolean> {
    return unwrap<boolean>(http.post(`${API_PREFIX}/backups/${encodeURIComponent(filename)}/restore`));
  },
};

/**
 * 通知接口。
 */
export const notificationsApi = {
  list(query: { page?: number; page_size?: number } = {}): Promise<PaginatedResponse<NotificationSetting>> {
    return unwrap<PaginatedResponse<NotificationSetting>>(
      http.get(`${API_PREFIX}/notifications`, { params: compactParams(query) })
    );
  },
  create(payload: NotificationPayload): Promise<NotificationSetting> {
    return unwrap<NotificationSetting>(http.post(`${API_PREFIX}/notifications`, payload));
  },
  update(id: number, payload: NotificationPayload): Promise<NotificationSetting> {
    return unwrap<NotificationSetting>(http.put(`${API_PREFIX}/notifications/${id}`, payload));
  },
  delete(id: number): Promise<null> {
    return unwrap<null>(http.delete(`${API_PREFIX}/notifications/${id}`));
  },
  test(id: number, message: string): Promise<null> {
    return unwrap<null>(http.post(`${API_PREFIX}/notifications/${id}/test`, { message }));
  },
};
