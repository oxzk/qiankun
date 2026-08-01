import { describe, expect, it } from "vitest";
import { buildSessionSnapshot } from "@/lib/session";
import type { TokenResponse } from "@/types";

describe("session helpers", () => {
  it("builds snapshot with expires_in", () => {
    const token: TokenResponse = {
      access_token: "abc",
      token_type: "bearer",
      expires_in: 120,
      user: { id: 1, username: "admin" },
    };
    const snapshot = buildSessionSnapshot(token, 1_000_000);
    expect(snapshot.token).toBe("abc");
    expect(snapshot.expiresAt).toBe(1_000_000 + 120_000);
    expect(snapshot.user).toEqual({ id: 1, username: "admin" });
  });
});
