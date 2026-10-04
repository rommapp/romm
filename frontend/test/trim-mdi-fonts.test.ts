// Dropping a rule that is needed blanks an icon in production, so anything
// unsure must be kept.
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  BACKEND_ICONS,
  buildIconAllowList,
  dropSourceMapComment,
  dropUnusedIcons,
  isUnusedIcon,
  keepOnlyWoff2,
  readSourceText,
  toLf,
  trimIconCss,
} from "../scripts/trim-mdi-fonts";

const UNUSED: string[] = []; // an empty allow list

// Vitest roots at frontend/.
const MDI_CSS = readFileSync(
  resolve(process.cwd(), "node_modules/@mdi/font/css/materialdesignicons.css"),
  "utf8",
);

describe("isUnusedIcon: drops a plain icon rule nobody uses", () => {
  it.each([
    [
      "half rule after a split on }",
      '.mdi-abacus::before {\n  content: "\\F16E0";\n',
    ],
    [
      "leading blank lines",
      '\n\n.mdi-abacus::before {\n  content: "\\F16E0";\n',
    ],
    [
      "CRLF line endings",
      '\r\n.mdi-abacus::before {\r\n  content: "\\F16E0";\r\n',
    ],
    ["tabs", '\t.mdi-abacus::before\t{\n\tcontent: "\\F16E0";'],
    [
      "with its closing brace",
      '.mdi-abacus::before {\n  content: "\\F16E0";\n}',
    ],
    ["minified", '.mdi-abacus::before{content:"\\F16E0"}'],
    [
      "digits in the name",
      '.mdi-numeric-1-box-multiple::before {\n  content: "\\F03A4";',
    ],
    ["short name", '.mdi-x::before {\n  content: "\\F1";'],
    [
      "content is not the first declaration",
      '.mdi-x::before {\n  color: red;\n  content: "\\F1";',
    ],
  ])("%s", (_label, rule) => {
    expect(isUnusedIcon(rule, UNUSED)).toBe(true);
  });
});

describe("isUnusedIcon: keeps an icon the source uses", () => {
  const rule = '.mdi-abacus::before {\n  content: "\\F16E0";';

  it.each([
    ["in a template", '<v-icon icon="mdi-abacus" />'],
    ["in a string", "const icon = 'mdi-abacus';"],
    ["in a comment", "// mdi-abacus"],
    ["as the start of a longer name", "mdi-abacus-circle"],
    ["as the end of a longer name", "mdi-big-mdi-abacus"],
  ])("%s", (_label, source) => {
    expect(isUnusedIcon(rule, buildIconAllowList(source))).toBe(false);
  });

  it("drops it when only a different icon is used", () => {
    expect(isUnusedIcon(rule, ["mdi-zebra"])).toBe(true);
  });

  it("keeps a prefix of a used name (over-keeps, never under-keeps)", () => {
    expect(
      isUnusedIcon('.mdi-account::before {\n  content: "\\F1";', [
        "mdi-account-circle",
      ]),
    ).toBe(false);
  });
});

describe("isUnusedIcon: keeps every helper rule from the package", () => {
  it.each([
    [
      "@font-face",
      '@font-face {\n  font-family: "Material Design Icons";\n  src: url("x");',
    ],
    [
      "base class, comma list",
      ".mdi:before,\n.mdi-set {\n  display: inline-block;",
    ],
    [
      "size helper",
      ".mdi-18px.mdi-set,\n.mdi-18px.mdi:before {\n  font-size: 18px;",
    ],
    ["dark", ".mdi-dark:before {\n  color: rgba(0, 0, 0, 0.54);"],
    ["spin", ".mdi-spin:before {\n  animation: mdi-spin 2s infinite linear;"],
    ["rotate", ".mdi-rotate-45 {\n  transform: rotate(45deg);"],
    ["rotate before", ".mdi-rotate-45:before {\n  transform: rotate(45deg);"],
    ["flip", ".mdi-flip-h:before {\n  transform: scaleX(-1);"],
    [
      "keyframes",
      "@keyframes mdi-spin {\n  0% {\n    transform: rotate(0deg);",
    ],
    ["keyframe step", "\n  100% {\n    transform: rotate(359deg);"],
  ])("%s", (_label, rule) => {
    expect(isUnusedIcon(rule, UNUSED)).toBe(false);
  });
});

describe("isUnusedIcon: keeps anything it is unsure about", () => {
  it.each([
    ["single colon", '.mdi-x:before {\n  content: "\\F1";'],
    ["comma list", '.mdi-a::before,\n.mdi-b::before {\n  content: "\\F1";'],
    ["compound class", '.mdi-a.mdi-b::before {\n  content: "\\F1";'],
    ["descendant selector", '.mdi-a .mdi-b::before {\n  content: "\\F1";'],
    ["child selector", '.mdi-a>.mdi-b::before {\n  content: "\\F1";'],
    ["not starting with .mdi-", '.foo .mdi-x::before {\n  content: "\\F1";'],
    ["leading comment", '/* c */ .mdi-x::before {\n  content: "\\F1";'],
    [
      "inside a media query",
      '@media print {\n  .mdi-x::before {\n    content: "\\F1";',
    ],
    ["::after", '.mdi-x::after {\n  content: "\\F1";'],
    ["pseudo-class after", '.mdi-x::before:hover {\n  content: "\\F1";'],
    ["no content declaration", ".mdi-x::before {\n  color: red;"],
    ["empty body", ".mdi-x::before {"],
    [
      "content inside a value",
      ".mdi-x::before {\n  background: url(content:x);",
    ],
    ["vendor content property", '.mdi-x::before {\n  -webkit-content: "\\F1";'],
    [
      "content with a space before the colon",
      '.mdi-x::before {\n  content : "\\F1";',
    ],
    ["uppercase name", '.mdi-X::before {\n  content: "\\F1";'],
    ["underscore in name", '.mdi-x_y::before {\n  content: "\\F1";'],
    ["empty name", '.mdi-::before {\n  content: "\\F1";'],
    ["no opening brace", ".mdi-x::before"],
    ["not mdi", '.fa-x::before {\n  content: "\\F1";'],
    ["empty string", ""],
    ["whitespace only", " \n\t "],
    ["closing brace only", "}"],
  ])("%s", (_label, rule) => {
    expect(isUnusedIcon(rule, UNUSED)).toBe(false);
  });
});

describe("dropUnusedIcons", () => {
  const css = `@font-face {
  font-family: "Material Design Icons";
  src: url("a.woff2") format("woff2");
}

.mdi:before,
.mdi-set {
  display: inline-block;
}

.mdi-abacus::before {
  content: "\\F16E0";
}

.mdi-zebra::before {
  content: "\\F0001";
}

.mdi-legacy:before {
  content: "\\F0005";
}

.mdi-rotate-45:before {
  transform: rotate(45deg);
}

@keyframes mdi-spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(359deg);
  }
}
`;

  it("removes unused icons and nothing else", () => {
    const out = dropUnusedIcons(css, ["mdi-abacus"]);
    expect(out).toContain(".mdi-abacus::before");
    expect(out).not.toContain(".mdi-zebra::before");
    for (const kept of [
      "@font-face",
      ".mdi:before,",
      ".mdi-legacy:before",
      ".mdi-rotate-45:before",
      "@keyframes mdi-spin",
      "100% {",
    ]) {
      expect(out).toContain(kept);
    }
  });

  it("returns the css unchanged when every icon is used", () => {
    expect(dropUnusedIcons(css, ["mdi-abacus", "mdi-zebra"])).toBe(css);
  });

  it("returns an empty string for an empty string", () => {
    expect(dropUnusedIcons("", UNUSED)).toBe("");
  });
});

describe("dropUnusedIcons on the real @mdi/font css", () => {
  const css = MDI_CSS;
  const pieces = css.split("}");
  const icons = pieces.filter((piece) => isUnusedIcon(piece, UNUSED));

  it("recognises the whole icon set", () => {
    expect(icons.length).toBeGreaterThan(7000);
    expect(icons.length).toBeLessThan(8000);
    for (const piece of icons) expect(piece).toMatch(/content:\s*"\\F/i);
  });

  it("with nothing used, removes only icon rules", () => {
    const out = dropUnusedIcons(css, UNUSED);
    expect(out).not.toContain("content:");
    expect(out.split("}")).toHaveLength(pieces.length - icons.length);
    for (const helper of [
      "@font-face",
      ".mdi-spin:before",
      ".mdi-rotate-45:before",
      ".mdi-flip-h:before",
      "@keyframes mdi-spin",
    ]) {
      expect(out).toContain(helper);
    }
  });

  it("with everything used, returns the css unchanged", () => {
    expect(dropUnusedIcons(css, buildIconAllowList(css))).toBe(css);
  });
});

describe("buildIconAllowList", () => {
  it("lists each icon name once, sorted", () => {
    const text = `<v-icon icon="mdi-zebra" /> mdi-abacus 'mdi-zebra' mdi-abacus`;
    expect(buildIconAllowList(text)).toEqual(["mdi-abacus", "mdi-zebra"]);
  });

  it("finds names in templates, strings, comments and python", () => {
    const text = [
      '<v-icon :icon="`mdi-close`" />',
      "const icon = 'mdi-sync';",
      "// mdi-abacus",
      'icon: str = "mdi-web-sync"',
    ].join("\n");
    expect(buildIconAllowList(text)).toEqual([
      "mdi-abacus",
      "mdi-close",
      "mdi-sync",
      "mdi-web-sync",
    ]);
  });

  it("ignores text that is not an icon name", () => {
    expect(buildIconAllowList("mdi- MDI-FOO mdi_foo icon-mdi")).toEqual([]);
  });

  it("returns an empty list for empty text", () => {
    expect(buildIconAllowList("")).toEqual([]);
  });
});

// The dev container mounts frontend/ alone; CI always has the whole repo,
// where the drift has to be caught.
const BACKEND_FILE = resolve(
  process.cwd(),
  "../backend/endpoints/responses/notification.py",
);
const BACKEND_REACHABLE = existsSync(BACKEND_FILE) || Boolean(process.env.CI);

describe("BACKEND_ICONS", () => {
  it.runIf(BACKEND_REACHABLE)("lists every icon the backend names", () => {
    const named = readFileSync(BACKEND_FILE, "utf8").match(/mdi-[a-z0-9-]+/g);
    for (const name of named ?? []) expect(BACKEND_ICONS).toContain(name);
  });
});

describe("readSourceText", () => {
  const source = readSourceText(process.cwd());

  it("includes icons from the app, the backend and Vuetify itself", () => {
    expect(source).toContain("mdi-close-circle"); // src/
    expect(source).toContain("mdi-sync"); // backend notification
    expect(source).toContain("mdi-checkbox-marked"); // Vuetify checkbox
  });

  it("does not read node_modules under src or the rest of the backend", () => {
    expect(source).not.toContain("mdi-zodiac-virgo");
  });
});

describe("dropUnusedIcons keeps what the app really needs", () => {
  it("trims the real css but keeps every icon Vuetify draws", () => {
    const allowList = buildIconAllowList(readSourceText(process.cwd()));
    const out = dropUnusedIcons(MDI_CSS, allowList);
    for (const name of ["checkbox-marked", "radiobox-marked", "paperclip"]) {
      expect(out).toContain(`.mdi-${name}::before`);
    }
    expect(out.length).toBeLessThan(MDI_CSS.length / 4);
  });
});

describe("keepOnlyWoff2", () => {
  const fontFace = `@font-face {
  font-family: "Material Design Icons";
  src: url("../fonts/x-webfont.eot?v=9.9.9");
  src: url("../fonts/x-webfont.eot?#iefix&v=9.9.9") format("embedded-opentype"), url("../fonts/x-webfont.woff2?v=9.9.9") format("woff2"), url("../fonts/x-webfont.woff?v=9.9.9") format("woff"), url("../fonts/x-webfont.ttf?v=9.9.9") format("truetype");
  font-weight: normal;
}`;

  it("leaves one src, the woff2, with the name and version from the input", () => {
    const out = keepOnlyWoff2(fontFace);
    expect(out.match(/src:/g)).toHaveLength(1);
    expect(out).toContain(
      'src: url("../../node_modules/@mdi/font/fonts/x-webfont.woff2?v=9.9.9") format("woff2");',
    );
  });

  it("keeps the other declarations in place", () => {
    const lines = keepOnlyWoff2(fontFace).split("\n");
    expect(lines[0]).toBe("@font-face {");
    expect(lines[1]).toContain("font-family");
    expect(lines[2]).toContain("src:");
    expect(lines[3]).toContain("font-weight");
  });

  it("throws when there is no woff2 url", () => {
    expect(() =>
      keepOnlyWoff2('@font-face {\n  font-family: "x";\n}'),
    ).toThrow();
  });

  it("throws when there is no font-family line", () => {
    const noFamily = fontFace.replace("font-family", "font-famly");
    expect(() => keepOnlyWoff2(noFamily)).toThrow();
  });

  it("leaves the real package css with exactly one src", () => {
    expect(keepOnlyWoff2(MDI_CSS).match(/src:/g)).toHaveLength(1);
  });
});

describe("dropSourceMapComment", () => {
  it("removes the sourceMappingURL line and nothing else", () => {
    const css = ".a { color: red; }\n/*# sourceMappingURL=x.css.map */";
    expect(dropSourceMapComment(css)).toBe(".a { color: red; }");
  });

  it("leaves css without one unchanged", () => {
    expect(dropSourceMapComment(".a { color: red; }")).toBe(
      ".a { color: red; }",
    );
  });

  it("removes it from the real package css", () => {
    expect(MDI_CSS).toContain("sourceMappingURL");
    expect(dropSourceMapComment(MDI_CSS)).not.toContain("sourceMappingURL");
  });
});

describe("line endings", () => {
  const css = [
    "@font-face {",
    '  font-family: "Material Design Icons";',
    '  src: url("../fonts/x.woff2?v=1") format("woff2");',
    "}",
    ".mdi-a::before {",
    '  content: "\\F1";',
    "}",
    ".mdi-b::before {",
    '  content: "\\F2";',
    "}",
    "",
  ];
  const lf = css.join("\n");
  const crlf = css.join("\r\n");

  it("toLf turns CRLF into LF and leaves LF alone", () => {
    expect(toLf("a\r\nb\r\n")).toBe("a\nb\n");
    expect(toLf("a\nb\n")).toBe("a\nb\n");
    expect(toLf("")).toBe("");
  });

  it("trimIconCss never returns a carriage return", () => {
    expect(trimIconCss(crlf, ["mdi-a"])).not.toContain("\r");
  });

  it("trimIconCss gives the same result for CRLF and LF input", () => {
    expect(trimIconCss(crlf, ["mdi-a"])).toBe(trimIconCss(lf, ["mdi-a"]));
  });

  it("still drops and keeps the right icons in CRLF input", () => {
    const out = trimIconCss(crlf, ["mdi-a"]);
    expect(out).toContain(".mdi-a::before");
    expect(out).not.toContain(".mdi-b::before");
  });

  it("trimIconCss output for the real package css has no carriage returns", () => {
    expect(trimIconCss(MDI_CSS, [])).not.toContain("\r");
  });

  it("a generated file read back with CRLF still matches after toLf", () => {
    const generated = trimIconCss(lf, ["mdi-a"]);
    const onDisk = generated.replaceAll("\n", "\r\n");
    expect(toLf(onDisk)).toBe(generated);
  });
});
