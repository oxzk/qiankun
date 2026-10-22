export type JsonRecord = Record<string, unknown>;

export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T | null;
}

/**
 * 后端返回的枚举选项。
 */
export interface EnumOption<TValue extends string = string> {
  /**
   * 枚举值。
   */
  value: TValue;
  /**
   * 前端展示文案。
   */
  label: string;
}

/**
 * 按字段名组织的枚举映射。
 */
export type EnumMap = Record<string, EnumOption[]>;

export interface PaginatedResponse<T> {
  items: T[];
  enums: EnumMap;
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: number;
  username: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface TaskStats {
  total_tasks: number;
  active_tasks: number;
  executions_by_status: Record<string, number>;
}

export type NotifyStrategy = "never" | "always" | "on_failure" | "on_success";

export type NotifyType = "webhook" | "telegram";

export interface NotificationSetting {
  id: number;
  name: string;
  notify_type: NotifyType;
  config: JsonRecord;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface NotificationPayload {
  name: string;
  notify_type: NotifyType;
  config: JsonRecord;
  enabled: boolean;
}

export interface TaskPayload {
  name: string;
  provider_name: string;
  provider_config: JsonRecord;
  cron_expression: string;
  enabled: boolean;
  timeout_seconds: number;
  retry_count: number;
  retry_interval: number;
  notification_ids: number[];
  notify_strategy: NotifyStrategy;
}

export interface Task extends TaskPayload {
  id: number;
  next_run_time: string | null;
  last_run_time: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export type ExecutionStatus = "running" | "success" | "failed" | "timeout" | "cancelled";
export type TriggerType = "auto" | "manual";

export interface Execution {
  id: number;
  task_id: number;
  task_name: string | null;
  provider_name: string;
  provider_config: JsonRecord;
  trigger_type: TriggerType;
  status: ExecutionStatus;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  retry_attempt: number;
  result_message: string | null;
  result_data: JsonRecord | null;
  logs: string[];
  error_message: string | null;
  error_traceback: string | null;
}

export interface ProviderInfo {
  name: string;
  code: string;
  enabled: boolean;
}

/**
 * Provider 创建和更新请求。
 */
export interface ProviderPayload {
  /**
   * Provider 名称。
   */
  name: string;
  /**
   * Provider 动态代码。
   */
  code: string;
  /**
   * 是否启用 Provider。
   */
  enabled: boolean;
}

export interface BackupInfo {
  /**
   * 备份文件名。
   */
  filename: string;
  /**
   * 备份创建时间。
   */
  created_at: string;
  /**
   * 备份文件大小。
   */
  size_bytes: number;
  /**
   * 各表记录数。
   */
  table_counts: Record<string, number>;
}

export interface ProviderValidateResult {
  valid: boolean;
  config: JsonRecord | null;
  error: string | null;
}

/**
 * Provider 执行结果。
 */
export interface ProviderResult {
  /**
   * 是否执行成功。
   */
  success: boolean;
  /**
   * 结果消息。
   */
  message: string;
  /**
   * 结果数据。
   */
  data: JsonRecord;
  /**
   * 执行日志。
   */
  logs: string[];
}
