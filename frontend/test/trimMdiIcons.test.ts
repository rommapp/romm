import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Plugin, ResolvedConfig } from "vite";
import { describe, expect, it, vi } from "vitest";
import { isMdiCss, listIconNames, trimMdiIcons } from "../scripts/trimMdiIcons";

const MDI_ID = resolve(
  process.cwd(),
  "node_modules/@mdi/font/css/materialdesignicons.css",
).replaceAll("\\", "/");
const MDI_CSS = readFileSync(MDI_ID, "utf8");

// Runs the plugin's hooks the way Vite does, without a Vite server.
function setup(command: "build" | "serve" = "build") {
  const plugin = trimMdiIcons() as Required<
    Pick<
      Plugin,
      | "configResolved"
      | "buildStart"
      | "transform"
      | "closeBundle"
      | "resolveId"
      | "load"
    >
  >;
  const info = vi.fn();
  const error = vi.fn((message: string) => {
    throw new Error(message);
  });
  const ctx = { info, error };

  (plugin.configResolved as (c: ResolvedConfig) => void)({
    root: process.cwd(),
    command,
  } as ResolvedConfig);
  (plugin.buildStart as () => void).call(ctx);

  const transform = (code: string, id: string) =>
    (
      plugin.transform as (
        this: typeof ctx,
        code: string,
        id: string,
      ) => { code: string } | null
    ).call(ctx, code, id);
  const closeBundle = () =>
    (plugin.closeBundle as (this: typeof ctx) => void).call(ctx);
  const resolveId = (id: string) =>
    (plugin.resolveId as (id: string) => string | undefined)(id);
  const load = (id: string) =>
    (plugin.load as (id: string) => string | undefined)(id);
  return { transform, closeBundle, info, resolveId, load };
}

describe("isMdiCss", () => {
  it("matches the package css only", () => {
    expect(isMdiCss(MDI_ID)).toBe(true);
    expect(isMdiCss(`${MDI_ID}?raw`)).toBe(false);
    expect(isMdiCss("/src/app.css")).toBe(false);
  });
});

describe("listIconNames", () => {
  it("lists plain glyph rules, sorted", () => {
    const css = [
      ".mdi-b::before { content: 'b'; }",
      ".mdi-a::before { content: 'a'; }",
      ".mdi-18px.mdi::before { font-size: 18px; }",
      ".mdi-spin { animation: mdi-spin 2s infinite linear; }",
    ].join("\n");
    expect(listIconNames(css)).toEqual(["mdi-a", "mdi-b"]);
  });
});

describe("virtual:mdi-icons", () => {
  it("resolves only its own id", () => {
    const { resolveId } = setup();
    expect(resolveId("virtual:mdi-icons")).toBe("\0virtual:mdi-icons");
    expect(resolveId("virtual:platform-icons")).toBeUndefined();
  });

  it("exports the names the trimmed css keeps", () => {
    const { transform, load } = setup();
    const code = load("\0virtual:mdi-icons")!;
    const names = JSON.parse(code.replace(/^export default (.*);$/s, "$1"));

    expect(names).toEqual(listIconNames(transform(MDI_CSS, MDI_ID)!.code));
    expect(names).toContain("mdi-checkbox-marked");
    expect(load("virtual:mdi-icons")).toBeUndefined();
  });
});

describe("trimMdiIcons transform", () => {
  it("trims the package css", () => {
    const { transform } = setup();
    const out = transform(MDI_CSS, MDI_ID)!.code;

    expect(out.length).toBeLessThan(MDI_CSS.length / 4);
    expect(out).toContain(".mdi-checkbox-marked::before");
    expect(out.match(/src:/g)).toHaveLength(1);
    expect(out).toContain('url("../fonts/');
  });

  it("logs one summary line at the end of a build", () => {
    const { transform, closeBundle, info } = setup("build");
    transform(MDI_CSS, MDI_ID);
    expect(info).not.toHaveBeenCalled();
    closeBundle();
    expect(info).toHaveBeenCalledOnce();
    expect(info.mock.calls[0]![0]).toMatch(
      /^\d+ icons -> \d+ \| \d+ KB -> \d+ KB$/,
    );
  });

  it("stays quiet in dev", () => {
    const { transform, closeBundle, info } = setup("serve");
    transform(MDI_CSS, MDI_ID);
    closeBundle();
    expect(info).not.toHaveBeenCalled();
  });

  it("leaves other files and query imports alone", () => {
    const { transform } = setup();
    expect(transform(MDI_CSS, "/src/app.css")).toBeNull();
    expect(transform(MDI_CSS, `${MDI_ID}?raw`)).toBeNull();
  });

  it("throws when no icon rule survives", () => {
    const { transform } = setup();
    const noIcons =
      '@font-face {\n  font-family: "Material Design Icons";\n  src: url("../fonts/x.woff2") format("woff2");\n}';
    expect(() => transform(noIcons, MDI_ID)).toThrow(
      /No icon rules survived trimming .*materialdesignicons\.css: the allow list had \d+ names/,
    );
  });
});
