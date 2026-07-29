import { describe, expect, it } from "vitest";
import { queryKeys } from "@/lib/query-keys";

describe("queryKeys", () => {
  it("keeps stable task list keys", () => {
    expect(queryKeys.tasks.list({ page: 1, name: "demo", enabled: "" })).toEqual([
      "tasks",
      "list",
      { page: 1, name: "demo", enabled: "" },
    ]);
    expect(queryKeys.tasks.root).toEqual(["tasks"]);
  });

  it("builds execution detail keys", () => {
    expect(queryKeys.executions.detail(42)).toEqual(["executions", "detail", 42]);
  });

  it("builds typed executions list keys", () => {
    expect(
      queryKeys.executions.list({
        page: 2,
        taskId: "12",
        taskName: "",
        status: "running",
      }),
    ).toEqual([
      "executions",
      "list",
      {
        page: 2,
        taskId: "12",
        taskName: "",
        status: "running",
      },
    ]);
  });
});
