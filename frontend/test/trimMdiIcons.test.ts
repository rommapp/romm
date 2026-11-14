import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  keptGlyphs,
  subsetIconFont,
  trimIconCss,
  usedIconNames,
  useSubsetFont,
} from "../scripts/trimMdiIcons";

const MDI_CSS = readFileSync(
  "node_modules/@mdi/font/css/materialdesignicons.css",
  "utf8",
);

describe("trimIconCss", () => {
  it("keeps used icon rules and the shared .mdi rules", () => {
    const css = trimIconCss(MDI_CSS, new Set(["mdi-account"]));

    expect(css).toContain(".mdi-account::before");
    expect(css).not.toContain(".mdi-account-circle::before");
    expect(css).toContain("@font-face");
    expect(css).toContain(".mdi-spin");
  });
});

describe("keptGlyphs", () => {
  it("returns the code point of each remaining icon", () => {
    const css = trimIconCss(MDI_CSS, new Set(["mdi-account"]));

    expect(keptGlyphs(css)).toBe("\u{F0004}");
  });
});

describe("useSubsetFont", () => {
  it("leaves one woff2 source and no other format", () => {
    const css = useSubsetFont(MDI_CSS, "../x/subset.woff2");

    expect(css).toContain('url("../x/subset.woff2") format("woff2")');
    expect(css).not.toContain(".eot");
    expect(css).not.toContain(".ttf");
    expect(css).toContain(".mdi-account::before");
  });
});

describe("subsetIconFont", () => {
  it("keeps only the requested glyphs", async () => {
    const full = readFileSync(
      "node_modules/@mdi/font/fonts/materialdesignicons-webfont.woff2",
    );

    const subset = await subsetIconFont(full, "\u{F0004}");

    expect(subset.length).toBeLessThan(full.length / 50);
  });
});

describe("usedIconNames", () => {
  it("finds the icons named in src", () => {
    const used = usedIconNames(".");

    expect(used).toContain("mdi-magnify");
  });
});
