import { describe, expect, it } from "vitest";
import { joinNames } from "./lists";

describe("joinNames", () => {
  it("joins in the reader's language, not with a hardcoded separator", () => {
    const names = ["File", "Core", "Full screen"];

    expect(joinNames(names, "en_US")).toBe("File, Core, and Full screen");
    expect(joinNames(names, "de_DE")).toBe("File, Core und Full screen");
    expect(joinNames(names, "ja_JP")).toBe("File、Core、Full screen");
  });

  it("leaves one name alone and answers nothing for none", () => {
    expect(joinNames(["Core"], "en_US")).toBe("Core");
    expect(joinNames([], "en_US")).toBe("");
  });

  // A phrase is not worth a render error, and the names are still the names.
  it("falls back to a plain list for a locale Intl will not take", () => {
    expect(joinNames(["File", "Core"], "not a locale")).toBe("File, Core");
  });

  it("takes the runtime's own locale when the caller has none", () => {
    expect(joinNames(["File", "Core"], null)).toContain("File");
  });
});
