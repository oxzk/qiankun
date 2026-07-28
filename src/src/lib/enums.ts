import type { EnumMap, EnumOption } from "@/types";

const fallbackLabels: Record<string, Record<string, string>> = {
  notify_strategy: {
    never: "不通知",
    always: "每次完成后通知",
    on_failure: "仅失败时通知",
    on_success: "仅成功时通知",
  },
  notify_type: {
    webhook: "Webhook",
    telegram: "Telegram",
  },
  status: {
    running: "运行中",
    success: "成功",
    failed: "失败",
    timeout: "超时",
    cancelled: "已取消",
  },
  trigger_type: {
    auto: "自动调度",
    manual: "手动触发",
  },
};

/**
 * 获取枚举选项, 优先使用接口返回的枚举元数据。
 */
export function enumOptions<TValue extends string>(
  enums: EnumMap | undefined,
  field: string,
): Array<EnumOption<TValue>> {
  const options = enums?.[field];
  if (options?.length) return options as Array<EnumOption<TValue>>;
  return Object.entries(fallbackLabels[field] ?? {}).map(([value, label]) => ({
    value: value as TValue,
    label,
  }));
}

/**
 * 获取枚举展示文案, 优先使用接口返回的枚举元数据。
 */
export function enumLabel(enums: EnumMap | undefined, field: string, value: string | null | undefined): string {
  if (!value) return "-";
  const option = enumOptions(enums, field).find((item) => item.value === value);
  return option?.label ?? value;
}
