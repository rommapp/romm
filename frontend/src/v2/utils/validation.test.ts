import { describe, expect, it, vi } from "vitest";
import { relativeFolderPath } from "./validation";

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
