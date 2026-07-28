import { describe, expect, it } from "vitest";
import { queryKeys } from "@/lib/query-keys";

describe("queryKeys", () => {
  it("keeps stable task list keys", () => {
    expect(queryKeys.tasks.list({ page: 1, name: "demo" })).toEqual(["tasks", { page: 1, name: "demo" }]);
    expect(queryKeys.tasks.root).toEqual(["tasks"]);
  });

  it("builds execution detail keys", () => {
    expect(queryKeys.executions.detail(42)).toEqual(["executions", "detail", 42]);
  });
});
