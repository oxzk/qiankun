import type { JsonRecord } from "@/types";

/**
 * 格式化 JSON 对象。
 */
export function formatJson(value: JsonRecord): string {
  return JSON.stringify(value, null, 2);
}

/**
 * 解析 JSON 对象文本。
 */
export function parseJsonObject(text: string): JsonRecord {
  const result = tryParseJsonObject(text);
  if (result.error || !result.value) throw new Error(result.error || "请输入有效的 JSON 对象格式。");
  return result.value;
}

/**
 * 尝试解析 JSON 对象, 返回值或错误文案。
 */
export function tryParseJsonObject(text: string): { value: JsonRecord; error: null } | { value: null; error: string } {
  if (!text.trim()) return { value: {}, error: null };
  try {
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, error: "请输入有效的 JSON 对象格式。" };
    }
    return { value: parsed as JsonRecord, error: null };
  } catch {
    return { value: null, error: "JSON 格式无效。" };
  }
}
