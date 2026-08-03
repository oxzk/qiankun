/**
 * 解析单个 cron 字段是否匹配目标值。
 */
function fieldMatches(field: string, value: number, min: number, max: number): boolean {
  if (field === "*") return true;
  return field.split(",").some((part) => {
    const stepParts = part.split("/");
    const rangePart = stepParts[0] ?? "*";
    const step = stepParts[1] ? Number(stepParts[1]) : 1;
    if (!Number.isInteger(step) || step <= 0) return false;

    let start = min;
    let end = max;
    if (rangePart !== "*") {
      if (rangePart.includes("-")) {
        const [rawStart, rawEnd] = rangePart.split("-");
        start = Number(rawStart);
        end = Number(rawEnd);
      } else {
        start = Number(rangePart);
        end = start;
      }
    }
    if (!Number.isInteger(start) || !Number.isInteger(end)) return false;
    if (start < min || end > max || start > end) return false;
    if (value < start || value > end) return false;
    return (value - start) % step === 0;
  });
}

/**
 * 判断时间是否匹配 5 段 cron 表达式。
 */
function matchesCron(expressionParts: string[], date: Date): boolean {
  const minute = date.getMinutes();
  const hour = date.getHours();
  const day = date.getDate();
  const month = date.getMonth() + 1;
  const weekday = date.getDay();
  const [minuteField, hourField, dayField, monthField, weekdayField] = expressionParts;
  return (
    fieldMatches(minuteField, minute, 0, 59) &&
    fieldMatches(hourField, hour, 0, 23) &&
    fieldMatches(dayField, day, 1, 31) &&
    fieldMatches(monthField, month, 1, 12) &&
    fieldMatches(weekdayField, weekday, 0, 6)
  );
}

/**
 * 计算 cron 表达式接下来若干次运行时间。
 * 仅支持标准 5 段表达式; 非法表达式返回空数组。
 */
export function getNextCronRuns(expression: string, count = 5, from: Date = new Date()): Date[] {
  const parts = expression.trim().split(/\s+/);
  if (parts.length !== 5 || count <= 0) return [];

  const cursor = new Date(from);
  cursor.setSeconds(0, 0);
  cursor.setMinutes(cursor.getMinutes() + 1);

  const results: Date[] = [];
  const maxSteps = 366 * 24 * 60;
  for (let step = 0; step < maxSteps && results.length < count; step += 1) {
    if (matchesCron(parts, cursor)) {
      results.push(new Date(cursor));
    }
    cursor.setMinutes(cursor.getMinutes() + 1);
  }
  return results;
}
