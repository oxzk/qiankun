import { describe, expect, it } from "vitest";
import { getNextCronRuns } from "@/lib/cron";

describe("getNextCronRuns", () => {
  it("returns empty for invalid expression", () => {
    expect(getNextCronRuns("invalid")).toEqual([]);
    expect(getNextCronRuns("* * *")).toEqual([]);
  });

  it("returns next runs for every-minute cron", () => {
    const from = new Date("2026-01-01T00:00:00");
    const runs = getNextCronRuns("* * * * *", 3, from);
    expect(runs).toHaveLength(3);
    expect(runs[0]?.getTime()).toBe(new Date("2026-01-01T00:01:00").getTime());
    expect(runs[1]?.getTime()).toBe(new Date("2026-01-01T00:02:00").getTime());
  });
});
