import { describe, expect, it } from "vitest";
import { compactParams, getErrorMessage } from "@/lib/http";

describe("http helpers", () => {
  it("compacts empty query params", () => {
    expect(compactParams({ a: 1, b: "", c: null, d: undefined, e: "ok" })).toEqual({ a: 1, e: "ok" });
  });

  it("extracts plain error message", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
    expect(getErrorMessage("x")).toBe("请求失败");
  });
});
