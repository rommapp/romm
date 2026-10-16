// Theme pack loading, validation and compilation.
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative, resolve, sep } from "node:path";
import { scopeSelectorList } from "./cssrefs.mjs";
import { SCOPES, isTokenName } from "./tokens.mjs";

export const PACK_ID = /^[a-z0-9][a-z0-9-]{0,63}$/;
export const RESERVED_IDS = new Set(["none", "index", "stock"]);

/** Files that only change through a build-time overlay, because nginx serves them outside /assets. */
export const ROOT_FILES = new Set([
  "/favicon.ico",
  "/favicon.svg",
  "/favicon-16x16.png",
  "/favicon-32x32.png",
  "/apple-touch-icon.png",
  "/android-chrome-192x192.png",
  "/android-chrome-512x512.png",
  "/safari-pinned-tab.svg",
]);

/** /assets subfolders that hold runtime code or library data, never theme artwork. */
export const EXCLUDED_ASSET_DIRS = [
  "emulatorjs",
  "ruffle",
  "jsdos",
  "pico8",
  "easyrpg",
  "gme",
  "patcherjs",
  "romm",
];

const ASSET_PATH = /^\/assets\/[A-Za-z0-9._/-]+$/;
const UNSAFE_VALUE = /[{};<>\\]/;
const VUETIFY_COLOR = /^[a-z][a-z0-9-]*$/;
const HEX = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i;
const isObject = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const FONT_FORMATS = { ".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype" };

export function listPacks(packsDir) {
  if (!existsSync(packsDir)) return [];
  return readdirSync(packsDir)
    .filter((name) => existsSync(join(packsDir, name, "theme.json")))
    .sort();
}

export function loadPack(dir) {
  const file = join(dir, "theme.json");
  const pack = JSON.parse(readFileSync(file, "utf8"));
  if (!isObject(pack)) throw new Error("theme.json must contain a JSON object");
  return { dir: resolve(dir), pack };
}

function insidePack(dir, rel) {
  const full = resolve(dir, rel);
  return full === dir || full.startsWith(dir + sep) ? full : null;
}

export function hexToRgbTriplet(hex) {
  let h = hex.slice(1);
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  const n = parseInt(h, 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

/** Applies token-aliases.json renames in place; returns one warning per rename. */
export function applyAliases(pack, aliases = {}) {
  const warnings = [];
  for (const scope of SCOPES) {
    const tokens = pack.tokens?.[scope];
    if (!isObject(tokens)) continue;
    for (const [oldName, newName] of Object.entries(aliases)) {
      if (!(oldName in tokens)) continue;
      if (!(newName in tokens)) tokens[newName] = tokens[oldName];
      delete tokens[oldName];
      warnings.push(`tokens.${scope}: ${oldName} was renamed upstream to ${newName}; update the pack`);
    }
  }
  return warnings;
}

/**
 * Validates a pack against the upstream catalog.
 * catalog = { tokens: Set<string>, assets: Set<string> } (either may be omitted to skip that check).
 */
export function validatePack({ dir, pack }, catalog = {}) {
  const errors = [];
  const warnings = [];
  const err = (m) => errors.push(m);

  if (typeof pack.id !== "string" || !PACK_ID.test(pack.id)) {
    err(`id must match ${PACK_ID} (lowercase letters, digits, dashes)`);
  } else if (RESERVED_IDS.has(pack.id)) {
    err(`id "${pack.id}" is reserved`);
  }
  if (typeof pack.name !== "string" || !pack.name.trim()) err("name is required");

  const section = (key) => {
    if (pack[key] === undefined) return {};
    if (isObject(pack[key])) return pack[key];
    err(`${key}: must be an object`);
    return {};
  };

  const tokens = section("tokens");
  for (const scope of Object.keys(tokens)) {
    if (!SCOPES.includes(scope)) {
      err(`tokens.${scope}: unknown scope (use ${SCOPES.join(", ")})`);
      continue;
    }
    if (!isObject(tokens[scope])) {
      err(`tokens.${scope}: must be an object of token names and values`);
      continue;
    }
    for (const [name, value] of Object.entries(tokens[scope])) {
      if (!isTokenName(name)) err(`tokens.${scope}: "${name}" is not a --r-* token name`);
      else if (catalog.tokens && !catalog.tokens.has(name)) {
        err(`tokens.${scope}: ${name} does not exist in this RomM release`);
      }
      if (typeof value !== "string" || !value.trim() || UNSAFE_VALUE.test(value)) {
        err(`tokens.${scope}.${name}: value must be a non-empty string without { } ; < > \\`);
      }
    }
  }

  const vuetify = section("vuetify");
  for (const mode of Object.keys(vuetify)) {
    if (mode !== "dark" && mode !== "light") {
      err(`vuetify.${mode}: use "dark" or "light"`);
      continue;
    }
    if (!isObject(vuetify[mode])) {
      err(`vuetify.${mode}: must be an object of color names and hex values`);
      continue;
    }
    for (const [name, value] of Object.entries(vuetify[mode])) {
      if (!VUETIFY_COLOR.test(name)) err(`vuetify.${mode}: bad color name "${name}"`);
      if (!HEX.test(value)) err(`vuetify.${mode}.${name}: must be a #rgb or #rrggbb hex color`);
    }
  }

  const checkFile = (where, key, rel) => {
    const full = typeof rel === "string" ? insidePack(dir, rel) : null;
    if (!full) return err(`${where}["${key}"]: source must be a path inside the pack`);
    if (!existsSync(full) || !statSync(full).isFile()) return err(`${where}["${key}"]: missing file ${rel}`);
    if (extname(full).toLowerCase() !== extname(key).toLowerCase()) {
      err(`${where}["${key}"]: source ${rel} must have the same extension as the file it replaces`);
    }
  };

  for (const [key, rel] of Object.entries(section("assets"))) {
    if (!ASSET_PATH.test(key) || key.includes("..")) {
      err(`assets["${key}"]: must be an /assets/... path`);
      continue;
    }
    const top = key.split("/")[2];
    if (EXCLUDED_ASSET_DIRS.includes(top)) {
      err(`assets["${key}"]: /assets/${top}/ holds runtime code or library data and can't be themed`);
      continue;
    }
    checkFile("assets", key, rel);
    if (catalog.assets && !catalog.assets.has(key)) {
      warnings.push(`assets["${key}"]: not a stock file, so the app will never request it`);
    }
  }

  for (const [key, rel] of Object.entries(section("rootFiles"))) {
    if (!ROOT_FILES.has(key)) {
      err(`rootFiles["${key}"]: allowed keys are ${[...ROOT_FILES].join(", ")}`);
      continue;
    }
    checkFile("rootFiles", key, rel);
  }

  if (pack.fonts !== undefined && !Array.isArray(pack.fonts)) err("fonts: must be a list");
  (Array.isArray(pack.fonts) ? pack.fonts : []).forEach((font, i) => {
    if (!font || typeof font.family !== "string" || UNSAFE_VALUE.test(font.family) || /["']/.test(font.family)) {
      err(`fonts[${i}].family: required, without quotes or { } ; < > \\`);
    }
    const full = typeof font?.src === "string" ? insidePack(dir, font.src) : null;
    if (!full || !existsSync(full)) err(`fonts[${i}].src: missing file inside the pack`);
    else if (!FONT_FORMATS[extname(full).toLowerCase()]) err(`fonts[${i}].src: use .woff2, .woff, .ttf or .otf`);
    for (const k of ["weight", "style", "display"]) {
      if (font?.[k] !== undefined && (typeof font[k] !== "string" || UNSAFE_VALUE.test(font[k]))) {
        err(`fonts[${i}].${k}: must be a plain string`);
      }
    }
  });

  if (section("pwa").themeColor !== undefined && !HEX.test(pack.pwa.themeColor)) {
    err("pwa.themeColor must be a hex color");
  }

  if (pack.extraCss !== undefined) {
    const full = typeof pack.extraCss === "string" ? insidePack(dir, pack.extraCss) : null;
    if (!full || !existsSync(full)) err("extraCss: missing file inside the pack");
    else {
      const text = readFileSync(full, "utf8");
      if (/<\/?style/i.test(text)) err("extraCss: must not contain <style> tags");
      warnings.push("custom CSS (extraCss) isn't checked against new RomM releases; recheck it after upgrading");
    }
  }

  return { errors, warnings };
}

function block(selectors, decls) {
  const lines = Object.entries(decls).map(([k, v]) => `  ${k}: ${v};`);
  if (!lines.length) return "";
  return `${selectors.join(",\n")} {\n${lines.join("\n")}\n}\n`;
}

/** Builds the selectors for each scope; specificity beats every upstream token rule. */
export function scopeSelectors(id) {
  const t = `:root[data-romm-theme="${id}"]`;
  return {
    common: [`${t}.r-v2`, `${t} .r-v2`],
    dark: [`${t}.r-v2.r-v2-dark`, `${t}.r-v2-dark .r-v2`],
    light: [`${t}.r-v2.r-v2-light`, `${t}.r-v2-light .r-v2`],
    "input-key": [`${t}[data-input="key"].r-v2`, `${t}[data-input="key"] .r-v2`],
    "input-pad": [`${t}[data-input="pad"].r-v2`, `${t}[data-input="pad"] .r-v2`],
  };
}

/**
 * Compiles a validated pack.
 * Returns { css, files: [{ from, to }], rootFiles: [{ from, to }], meta, hash } with `to` relative to the output root.
 */
export function compilePack({ dir, pack }, { cssReferences = {} } = {}) {
  const id = pack.id;
  const base = `/themes/${id}`;
  const files = [];
  const parts = [`/* Generated by themeable from packs/${id}/theme.json. Do not edit. */\n`];

  for (const font of pack.fonts ?? []) {
    const rel = relative(dir, resolve(dir, font.src)).split(sep).join("/");
    files.push({ from: resolve(dir, font.src), to: `themes/${id}/${rel}` });
    const format = FONT_FORMATS[extname(rel).toLowerCase()];
    const props = [
      `  font-family: "${font.family}";`,
      `  src: url("${base}/${rel}") format("${format}");`,
      `  font-display: ${font.display ?? "swap"};`,
    ];
    if (font.weight) props.push(`  font-weight: ${font.weight};`);
    if (font.style) props.push(`  font-style: ${font.style};`);
    parts.push(`@font-face {\n${props.join("\n")}\n}\n`);
  }

  const selectors = scopeSelectors(id);
  for (const scope of SCOPES) {
    parts.push(block(selectors[scope], pack.tokens?.[scope] ?? {}));
  }

  for (const mode of ["dark", "light"]) {
    const colors = pack.vuetify?.[mode];
    if (!colors) continue;
    const decls = Object.fromEntries(
      Object.entries(colors).map(([k, v]) => [`--v-theme-${k}`, hexToRgbTriplet(v)]),
    );
    parts.push(block([`:root[data-romm-theme="${id}"] .v-theme--${mode}`], decls));
  }

  if (pack.extraCss) {
    const extra = readFileSync(resolve(dir, pack.extraCss), "utf8");
    parts.push(`/* custom CSS (extraCss) */\n:root[data-romm-theme="${id}"] {\n${extra}\n}\n`);
  }

  const scope = `:root[data-romm-theme="${id}"]`;
  const inlined = [];
  for (const [key, rel] of Object.entries(pack.assets ?? {})) {
    files.push({ from: resolve(dir, rel), to: `themes/${id}${key}` });
    const fileVersion = createHash("sha256").update(readFileSync(resolve(dir, rel))).digest("hex").slice(0, 10);
    const target = `${base}${key}?v=${fileVersion}`;
    for (const ref of cssReferences[key] ?? []) {
      const value = ref.value.split(key).join(target);
      let rule = `${scopeSelectorList(ref.selector, scope)} {\n  ${ref.property}: ${value};\n}\n`;
      for (const at of [...ref.atRules].reverse()) rule = `${at} {\n${rule}}\n`;
      inlined.push(`/* ${key} from ${ref.file} */\n${rule}`);
    }
  }
  if (inlined.length) parts.push(`/* Artwork the app bundle inlines, re-pointed at this pack. */\n${inlined.join("\n")}`);
  const rootFiles = Object.entries(pack.rootFiles ?? {}).map(([key, rel]) => ({
    from: resolve(dir, rel),
    to: key.slice(1),
  }));

  const css = parts.filter(Boolean).join("\n");
  const hash = createHash("sha256");
  hash.update(css);
  for (const f of [...files, ...rootFiles]) hash.update(f.to).update(readFileSync(f.from));
  const version = hash.digest("hex").slice(0, 12);

  const meta = {
    id,
    name: pack.name,
    description: pack.description ?? "",
    author: pack.author ?? "",
    version: pack.version ?? "0.0.0",
    css: `${base}/theme.css?v=${version}`,
    themeColor: pack.pwa?.themeColor ?? null,
    hasAssets: Object.keys(pack.assets ?? {}).length > 0,
  };
  return { css, files, rootFiles, meta, hash: version };
}
