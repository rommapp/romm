import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { trimIconCss, usedIconNames } from "../scripts/trimMdiIcons";

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

describe("usedIconNames", () => {
  it("finds icons from src and the ones Vuetify draws", () => {
    const used = usedIconNames(".");

    expect(used).toContain("mdi-magnify");
    expect(used).toContain("mdi-checkbox-marked");
  });
});
