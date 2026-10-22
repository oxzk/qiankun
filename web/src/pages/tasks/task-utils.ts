import { enumLabel, enumOptions } from "@/lib/enums";
import type { EnumMap, NotifyStrategy, Task, TaskPayload } from "@/types";

export const defaultTaskPayload: TaskPayload = {
  name: "",
  provider_name: "",
  provider_config: {},
  cron_expression: "*/5 * * * *",
  enabled: true,
  timeout_seconds: 300,
  retry_count: 0,
  retry_interval: 60,
  notification_ids: [],
  notify_strategy: "never",
};

/**
 * 构建任务更新请求数据。
 */
export function buildTaskPayload(task: Task, enabled: boolean): TaskPayload {
  return {
    name: task.name,
    provider_name: task.provider_name,
    provider_config: task.provider_config,
    cron_expression: task.cron_expression,
    enabled: enabled,
    timeout_seconds: task.timeout_seconds,
    retry_count: task.retry_count,
    retry_interval: task.retry_interval,
    notification_ids: task.notification_ids || [],
    notify_strategy: task.notify_strategy,
  };
}

/**
 * 任务弹窗初始数据。
 */
export function toTaskDialogPayload(task: Task | null): TaskPayload {
  if (!task) return defaultTaskPayload;
  return {
    name: task.name,
    provider_name: task.provider_name,
    provider_config: task.provider_config || {},
    cron_expression: task.cron_expression,
    enabled: task.enabled,
    timeout_seconds: task.timeout_seconds,
    retry_count: task.retry_count,
    retry_interval: task.retry_interval,
    notification_ids: task.notification_ids || [],
    notify_strategy: task.notify_strategy,
  };
}

/**
 * 获取通知策略选项。
 */
export function getNotifyStrategyOptions(enums: EnumMap | undefined): Array<{ value: NotifyStrategy; label: string }> {
  return enumOptions<NotifyStrategy>(enums, "notify_strategy");
}

/**
 * 格式化通知渠道描述。
 */
export function formatNotificationName(type: string, enums: EnumMap | undefined): string {
  return enumLabel(enums, "notify_type", type);
}
