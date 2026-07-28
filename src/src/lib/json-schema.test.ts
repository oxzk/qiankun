import { describe, expect, it } from "vitest";
import { parseJsonObject, tryParseJsonObject } from "@/lib/json-schema";

describe("json-schema", () => {
  it("parses empty text as empty object", () => {
    expect(parseJsonObject("")).toEqual({});
    expect(tryParseJsonObject("   ")).toEqual({ value: {}, error: null });
  });

  it("rejects non-object json", () => {
    expect(tryParseJsonObject("[]").error).toBeTruthy();
    expect(tryParseJsonObject('"text"').error).toBeTruthy();
    expect(() => parseJsonObject("{")).toThrow();
  });

  it("accepts object json", () => {
    expect(parseJsonObject('{"a":1}')).toEqual({ a: 1 });
  });
});
