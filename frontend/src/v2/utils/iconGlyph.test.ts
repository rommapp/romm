import { describe, expect, it, vi } from "vitest";
import { hasIconGlyph } from "@/v2/utils/iconGlyph";

function contentIs(content: string) {
  return vi
    .spyOn(globalThis, "getComputedStyle")
    .mockReturnValue({ content } as CSSStyleDeclaration);
}

describe("hasIconGlyph", () => {
  it("is true when the css gives the icon a glyph", () => {
    contentIs('"\\F0156"');

    expect(hasIconGlyph("mdi-glyph-drawn")).toBe(true);
  });

  it("is false when the css has no rule for the icon", () => {
    contentIs("none");

    expect(hasIconGlyph("mdi-glyph-none")).toBe(false);
  });

  it("is false for the normal content value too", () => {
    contentIs("normal");

    expect(hasIconGlyph("mdi-glyph-normal")).toBe(false);
  });

  it("keeps the icon when the environment cannot read pseudo-elements", () => {
    contentIs("");

    expect(hasIconGlyph("mdi-glyph-unreadable")).toBe(true);
  });

  it("asks the browser once per name", () => {
    const spy = contentIs("none");

    hasIconGlyph("mdi-glyph-cached");
    hasIconGlyph("mdi-glyph-cached");

    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("leaves nothing behind in the document", () => {
    contentIs('"\\F0156"');

    hasIconGlyph("mdi-glyph-clean");

    expect(document.querySelector("i.mdi-glyph-clean")).toBeNull();
  });

  it.each([
    ["not an mdi name", "fa-home"],
    ["extra classes", "mdi-a mdi-b"],
    ["uppercase", "mdi-Home"],
    ["empty", ""],
  ])("is false for %s without touching the document", (_label, name) => {
    const spy = contentIs('"\\F0156"');

    expect(hasIconGlyph(name)).toBe(false);
    expect(spy).not.toHaveBeenCalled();
  });
});
