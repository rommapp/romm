import { describe, expect, it, vi } from "vitest";
import { integerBetween, relativeFolderPath } from "./validation";

vi.mock("@/locales", () => ({
  default: { global: { t: (key: string) => key } },
}));

describe("relativeFolderPath", () => {
  it.each(["hack", "hack/v2", "patches/v2/", " cheats "])(
    "accepts %j",
    (value) => {
      expect(relativeFolderPath(value)).toBe(true);
    },
  );

  it.each(["/hack", "a\\b", "../x", "a/../b", "a//b", "a/./b", "."])(
    "rejects %j",
    (value) => {
      expect(relativeFolderPath(value)).toBe("common.invalid-relative-path");
    },
  );
});

describe("integerBetween", () => {
  const rule = integerBetween(1, 60);

  it.each([1, 60, "15", " 30 "])("accepts %j", (value) => {
    expect(rule(value)).toBe(true);
  });

  it.each([0, 61, "1.5", "", "abc", null, undefined])("rejects %j", (value) => {
    expect(rule(value)).toBe("common.integer-range");
  });
});
