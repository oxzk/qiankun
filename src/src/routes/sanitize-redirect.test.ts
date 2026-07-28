import { describe, expect, it } from "vitest";
import { ROOT_PATH, sanitizeRedirectPath } from "@/routes";

describe("sanitizeRedirectPath", () => {
  it("falls back to root for empty or unsafe values", () => {
    expect(sanitizeRedirectPath(null)).toBe(ROOT_PATH);
    expect(sanitizeRedirectPath("")).toBe(ROOT_PATH);
    expect(sanitizeRedirectPath("//evil.example")).toBe(ROOT_PATH);
    expect(sanitizeRedirectPath("https://evil.example")).toBe(ROOT_PATH);
    expect(sanitizeRedirectPath("/login")).toBe(ROOT_PATH);
  });

  it("keeps safe in-app paths", () => {
    expect(sanitizeRedirectPath("/tasks")).toBe("/tasks");
    expect(sanitizeRedirectPath("/executions?task_id=1")).toBe("/executions?task_id=1");
  });
});
