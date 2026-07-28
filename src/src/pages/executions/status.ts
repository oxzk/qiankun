import { enumLabel } from "@/lib/enums";
import type { EnumMap, ExecutionStatus, TriggerType } from "@/types";

/**
 * 执行状态中文文案。
 */
export function executionStatusLabel(status: ExecutionStatus, enums: EnumMap | undefined): string {
  return enumLabel(enums, "status", status);
}

/**
 * 触发类型中文文案。
 */
export function triggerTypeLabel(triggerType: TriggerType, enums: EnumMap | undefined): string {
  return enumLabel(enums, "trigger_type", triggerType);
}

/**
 * 执行状态徽标样式。
 */
export function executionStatusVariant(status: ExecutionStatus): "default" | "secondary" | "destructive" | "outline" {
  if (status === "success") return "default";
  if (status === "failed" || status === "timeout") return "destructive";
  if (status === "running") return "outline";
  return "secondary";
}
