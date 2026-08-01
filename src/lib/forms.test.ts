import { describe, expect, it } from "vitest";
import { passwordFormSchema, providerFormSchema, taskFormSchema, toTaskPayload } from "@/lib/forms";

describe("forms schemas", () => {
  it("accepts valid task form values", () => {
    const parsed = taskFormSchema.safeParse({
      name: "demo",
      provider_name: "probe",
      provider_config_text: '{"a":1}',
      cron_expression: "*/5 * * * *",
      enabled: true,
      timeout_seconds: 30,
      retry_count: 1,
      retry_interval: 10,
      notification_ids: [1],
      notify_strategy: "always",
    });
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(toTaskPayload(parsed.data).provider_config).toEqual({ a: 1 });
    }
  });

  it("rejects invalid provider config json", () => {
    const parsed = taskFormSchema.safeParse({
      name: "demo",
      provider_name: "probe",
      provider_config_text: "[1]",
      cron_expression: "*/5 * * * *",
      enabled: true,
      timeout_seconds: 30,
      retry_count: 0,
      retry_interval: 10,
      notification_ids: [],
      notify_strategy: "never",
    });
    expect(parsed.success).toBe(false);
  });

  it("validates provider form", () => {
    expect(providerFormSchema.safeParse({ name: "x", code: "class A: pass", enabled: true }).success).toBe(true);
    expect(providerFormSchema.safeParse({ name: " ", code: "", enabled: true }).success).toBe(false);
  });

  it("validates password confirmation", () => {
    expect(
      passwordFormSchema.safeParse({
        oldPassword: "a",
        newPassword: "b",
        confirmPassword: "b",
      }).success,
    ).toBe(true);
    expect(
      passwordFormSchema.safeParse({
        oldPassword: "a",
        newPassword: "b",
        confirmPassword: "c",
      }).success,
    ).toBe(false);
  });
});
