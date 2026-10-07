import { describe, expect, it } from "vitest";
import { hasIconGlyph } from "@/v2/utils/iconGlyph";
import { mockPseudoContent } from "@/v2/utils/iconGlyph.fixtures";

describe("hasIconGlyph", () => {
  it("is true when the css gives the icon a glyph", () => {
    mockPseudoContent('"\\F0156"');

    expect(hasIconGlyph("mdi-glyph-drawn")).toBe(true);
  });

  it("is false when the css has no rule for the icon", () => {
    mockPseudoContent("none");

    expect(hasIconGlyph("mdi-glyph-none")).toBe(false);
  });

  it("is false for the normal content value too", () => {
    mockPseudoContent("normal");

    expect(hasIconGlyph("mdi-glyph-normal")).toBe(false);
  });

  it("keeps the icon when the environment cannot read pseudo-elements", () => {
    mockPseudoContent("");

    expect(hasIconGlyph("mdi-glyph-unreadable")).toBe(true);
  });

  it("asks the browser once per name", () => {
    const spy = mockPseudoContent("none");

    hasIconGlyph("mdi-glyph-cached");
    hasIconGlyph("mdi-glyph-cached");

    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("leaves nothing behind in the document", () => {
    mockPseudoContent('"\\F0156"');

    hasIconGlyph("mdi-glyph-clean");

    expect(document.querySelector("i.mdi-glyph-clean")).toBeNull();
  });

  it.each([
    ["not an mdi name", "fa-home"],
    ["extra classes", "mdi-a mdi-b"],
    ["uppercase", "mdi-Home"],
    ["empty", ""],
  ])("is false for %s without touching the document", (_label, name) => {
    const spy = mockPseudoContent('"\\F0156"');

    expect(hasIconGlyph(name)).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});
