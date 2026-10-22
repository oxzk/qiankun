import { z } from "zod";
import type { NotifyStrategy, ProviderPayload, TaskPayload } from "@/types";
import { tryParseJsonObject } from "@/lib/json-schema";

/**
 * 任务表单 schema。
 */
export const taskFormSchema = z.object({
  name: z.string().trim().min(1, "任务名称不能为空"),
  provider_name: z.string().trim().min(1, "请选择执行器"),
  provider_config_text: z.string(),
  cron_expression: z.string().trim().min(1, "Cron 表达式不能为空"),
  enabled: z.boolean(),
  timeout_seconds: z.number().int().min(1).max(86400),
  retry_count: z.number().int().min(0).max(10),
  retry_interval: z.number().int().min(1).max(86400),
  notification_ids: z.array(z.number().int().positive()),
  notify_strategy: z.enum(["never", "always", "on_failure", "on_success"]),
}).superRefine((value, ctx) => {
  const parsed = tryParseJsonObject(value.provider_config_text);
  if (parsed.error) {
    ctx.addIssue({
      code: "custom",
      path: ["provider_config_text"],
      message: parsed.error,
    });
  }
});

/**
 * 任务表单值类型。
 */
export type TaskFormValues = z.infer<typeof taskFormSchema>;

/**
 * 将任务表单值转换为提交载荷。
 */
export function toTaskPayload(values: TaskFormValues): TaskPayload {
  const parsed = tryParseJsonObject(values.provider_config_text);
  return {
    name: values.name.trim(),
    provider_name: values.provider_name,
    provider_config: parsed.value ?? {},
    cron_expression: values.cron_expression.trim(),
    enabled: values.enabled,
    timeout_seconds: values.timeout_seconds,
    retry_count: values.retry_count,
    retry_interval: values.retry_interval,
    notification_ids: values.notify_strategy === "never" ? [] : values.notification_ids,
    notify_strategy: values.notify_strategy as NotifyStrategy,
  };
}

/**
 * 执行器表单 schema。
 */
export const providerFormSchema = z.object({
  name: z.string().trim().min(1, "执行器名称不能为空"),
  code: z.string().trim().min(1, "Provider 代码不能为空"),
  enabled: z.boolean(),
});

/**
 * 执行器表单值类型。
 */
export type ProviderFormValues = z.infer<typeof providerFormSchema>;

/**
 * 将执行器表单值转换为提交载荷。
 */
export function toProviderPayload(values: ProviderFormValues): ProviderPayload {
  return {
    name: values.name.trim(),
    code: values.code,
    enabled: values.enabled,
  };
}

/**
 * 修改密码表单 schema。
 */
export const passwordFormSchema = z
  .object({
    oldPassword: z.string().min(1, "请输入旧密码"),
    newPassword: z.string().min(1, "请输入新密码"),
    confirmPassword: z.string().min(1, "请再次输入新密码"),
  })
  .refine((value) => value.newPassword === value.confirmPassword, {
    message: "两次输入的密码不一致",
    path: ["confirmPassword"],
  });

/**
 * 修改密码表单值类型。
 */
export type PasswordFormValues = z.infer<typeof passwordFormSchema>;
