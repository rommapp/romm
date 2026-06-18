/**
 * build-tokens — emits src/v2/styles/tokens.css from src/v2/tokens/index.ts.
 *
 * The TypeScript module is the single source of truth. This script declares
 * the JS-path → CSS-variable mapping and writes the CSS file. Run it via
 * `npm run build:tokens` (also wired into predev / prebuild).
 *
 * Adding a new token: add it to src/v2/tokens/index.ts, then add a mapping
 * entry below if the default convention does not produce the desired CSS
 * variable name. Re-run `npm run build:tokens`.
 */
import { writeFile, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  colorBrand,
  colorCanvas,
  colorDark,
  colorLight,
  colorOverlay,
  colorProvider,
  colorStatus,
  colorStatusBase,
  elevation,
  focus,
  fontFamily,
  fontSize,
  fontWeight,
  layout,
  lineHeight,
  motion,
  radius,
  space,
  zIndex,
} from "../src/v2/tokens/index.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT = resolve(__dirname, "../src/v2/styles/tokens.css");

function camelToKebab(s: string): string {
  return s.replace(/([A-Z])/g, "-$1").toLowerCase();
}

type Entry = [cssName: string, value: string];

const NAME_OVERRIDES = {
  space: { rowPad: "--r-row-pad" },
  layout: {
    navHeight: "--r-nav-h",
    bottomNavHeight: "--r-bottom-nav-h",
    bottomNavMaxWidth: "--r-bottom-nav-max-w",
    touchTarget: "--r-touch-target",
    rowPad: null, // duplicate of --r-row-pad (space.rowPad), skip
    pageMaxWidth: "--r-page-max-w",
    cardArtWidth: "--r-card-art-w",
    cardArtHeight: "--r-card-art-h",
    cardArtWidthXs: "--r-card-art-w-xs",
    cardArtHeightXs: "--r-card-art-h-xs",
    cardArtWidthSm: "--r-card-art-w-sm",
    cardArtHeightSm: "--r-card-art-h-sm",
    cardArtWidthLg: "--r-card-art-w-lg",
    cardArtHeightLg: "--r-card-art-h-lg",
    cardArtWidthXl: "--r-card-art-w-xl",
    cardArtHeightXl: "--r-card-art-h-xl",
    heroCardWidth: "--r-hero-w",
    heroCardHeight: "--r-hero-h",
    heroCardWidthXs: "--r-hero-w-xs",
    heroCardHeightXs: "--r-hero-h-xs",
    heroCardWidthSm: "--r-hero-w-sm",
    heroCardHeightSm: "--r-hero-h-sm",
    heroCardWidthLg: "--r-hero-w-lg",
    heroCardHeightLg: "--r-hero-h-lg",
    heroCardWidthXl: "--r-hero-w-xl",
    heroCardHeightXl: "--r-hero-h-xl",
    detailCoverWidth: "--r-cover-w",
    listRowHeight: "--r-list-row-h",
    listHeaderHeight: "--r-list-header-h",
  },
  colorBrand: {
    fav: "--r-color-fav",
    avatarGradient: "--r-color-avatar-gradient",
    rommRed: "--r-color-romm-red",
    rommGreen: "--r-color-romm-green",
    rommBlue: "--r-color-romm-blue",
    rommGold: "--r-color-romm-gold",
  },
  // Stacking-layer tokens drop the "-index" suffix the default generator
  // would produce — components consume `--r-z-menu` etc., shorter and
  // matches the convention from §VI of the constitution.
  zIndex: {
    drawer: "--r-z-drawer",
    dialog: "--r-z-dialog",
    menu: "--r-z-menu",
    tooltip: "--r-z-tooltip",
    snackbar: "--r-z-snackbar",
  },
} as const;

function name(
  group: keyof typeof NAME_OVERRIDES | string,
  key: string,
  defaultPrefix: string,
): string | null {
  const overrides = (
    NAME_OVERRIDES as Record<string, Record<string, string | null>>
  )[group];
  if (overrides && key in overrides) return overrides[key];
  return `${defaultPrefix}-${camelToKebab(key)}`;
}

function entriesFor<T extends Record<string, string>>(
  obj: T,
  group: string,
  defaultPrefix: string,
): Entry[] {
  const out: Entry[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const cssName = name(group, k, defaultPrefix);
    if (cssName === null) continue;
    out.push([cssName, v]);
  }
  return out;
}

function lowerHex(value: string): string {
  // CSS convention: hex literals lowercase. TS source uses #ABCDEF for
  // readability; normalise on output.
  return value.replace(/#[0-9A-Fa-f]{3,8}\b/g, (m) => m.toLowerCase());
}

function block(selector: string, lines: Entry[], comment?: string): string {
  const indent = "  ";
  const body = lines
    .map(([n, v]) => `${indent}${n}: ${lowerHex(v)};`)
    .join("\n");
  return `${comment ? `/* ${comment} */\n` : ""}${selector} {\n${body}\n}\n`;
}

const SHARED: Entry[] = [
  ...entriesFor(colorBrand, "colorBrand", "--r-color-brand"),
  ...entriesFor(colorStatus, "colorStatus", "--r-color"),
  ...entriesFor(colorStatusBase, "colorStatusBase", "--r-color-status-base"),
  ...entriesFor(colorProvider, "colorProvider", "--r-color-provider"),
  ...entriesFor(colorOverlay, "colorOverlay", "--r-color-overlay"),
  ...entriesFor(colorCanvas, "colorCanvas", "--r-color-canvas"),
  ...entriesFor(fontFamily, "fontFamily", "--r-font-family"),
  ...entriesFor(fontSize, "fontSize", "--r-font-size"),
  ...entriesFor(lineHeight, "lineHeight", "--r-line-height"),
  ...entriesFor(fontWeight, "fontWeight", "--r-font-weight"),
  ...entriesFor(space, "space", "--r-space"),
  ...entriesFor(radius, "radius", "--r-radius"),
  ...entriesFor(elevation, "elevation", "--r-elev"),
  ...entriesFor(motion, "motion", "--r-motion"),
  // Default focus ring width is the mouse value; key/pad override below.
  ["--r-focus-ring-width", focus.ringWidthMouse],
  ["--r-focus-ring-offset", focus.ringOffset],
  ...entriesFor(layout, "layout", "--r-layout"),
  ...entriesFor(zIndex, "zIndex", "--r-z-index"),
];

const DARK: Entry[] = entriesFor(colorDark, "colorDark", "--r-color");
const LIGHT: Entry[] = entriesFor(colorLight, "colorLight", "--r-color");

const HEADER = `/*
 * RomM v2 Design Tokens — CSS Custom Properties
 *
 * GENERATED FILE — do not hand-edit. Source: src/v2/tokens/index.ts
 * Regenerate with: npm run build:tokens
 *
 * Scoped under .r-v2 so v1 styling is unaffected. Theme palettes live under
 * .r-v2.r-v2-dark and .r-v2.r-v2-light. The classes are toggled on <html>
 * by RomM.vue so teleported overlays (RDialog, RMenu, RTooltip) — which
 * land in <body> outside the app root — still resolve var(--r-color-*).
 */
`;

const css = [
  HEADER,
  block(".r-v2", SHARED),
  "",
  `html[data-input="key"] .r-v2 {`,
  `  --r-focus-ring-width: ${focus.ringWidthKey};`,
  `}`,
  `html[data-input="pad"] .r-v2 {`,
  `  --r-focus-ring-width: ${focus.ringWidthPad};`,
  `}`,
  "",
  block(
    ".r-v2.r-v2-dark",
    DARK,
    "Dark surface palette — translucent white over the near-black base.",
  ),
  block(
    ".r-v2.r-v2-light",
    LIGHT,
    "Light surface palette — translucent black over the off-white base.",
  ),
].join("\n");

async function main() {
  const existing = await readFile(OUTPUT, "utf-8").catch(() => "");
  if (existing === css) {
    process.stdout.write("tokens.css up-to-date\n");
    return;
  }
  await writeFile(OUTPUT, css, "utf-8");
  process.stdout.write(`tokens.css regenerated (${css.length} bytes)\n`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
