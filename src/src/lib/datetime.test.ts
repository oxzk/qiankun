import { describe, expect, it } from "vitest";
import { formatByteSize, formatDuration, formatDurationMs } from "@/lib/datetime";

describe("datetime helpers", () => {
  it("formats duration seconds", () => {
    expect(formatDuration(null)).toBe("-");
    expect(formatDuration(12)).toBe("12s");
    expect(formatDuration(75)).toBe("1m 15s");
  });

  it("formats duration milliseconds", () => {
    expect(formatDurationMs(null)).toBe("-");
    expect(formatDurationMs(1500)).toBe("2s");
    expect(formatDurationMs(61000)).toBe("1m 1s");
  });

  it("formats byte size", () => {
    expect(formatByteSize(512)).toBe("512 B");
    expect(formatByteSize(2048)).toBe("2.0 KB");
    expect(formatByteSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});
