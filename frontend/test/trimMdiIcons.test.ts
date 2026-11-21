import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  trimIconCss,
  unknownIconNames,
  usedIconNames,
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

describe("usedIconNames", () => {
  it("finds the icons named in src", () => {
    const used = usedIconNames(".");

    expect(used).toContain("mdi-magnify");
  });
});

describe("unknownIconNames", () => {
  it("reports names built at runtime or missing from @mdi/font", () => {
    const root = mkdtempSync(join(tmpdir(), "mdi-"));
    mkdirSync(join(root, "src"));
    writeFileSync(
      join(root, "src", "a.ts"),
      [
        'const a = "mdi-account mdi-spin";',
        'const b = "mdi-" + name;',
        "const c = `mdi-home-${state}`;",
        'const d = "mdi-not-an-icon";',
        "const e = `amdi-${id} my_mdi-${id}`;",
      ].join("\n"),
    );
    writeFileSync(
      join(root, "src", "a.test.ts"),
      "expect(x).toMatch(/^mdi-/);",
    );

    expect(unknownIconNames(root, MDI_CSS)).toEqual([
      join("src", "a.ts") + ":2 mdi-",
      join("src", "a.ts") + ":3 mdi-home-",
      join("src", "a.ts") + ":4 mdi-not-an-icon",
    ]);
  });

  it("finds none in src", () => {
    expect(unknownIconNames(".", MDI_CSS)).toEqual([]);
  });
});
