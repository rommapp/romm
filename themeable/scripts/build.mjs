#!/usr/bin/env node
// Compiles every pack in packs/ into a web root fragment:
//   <out>/themes/<id>/theme.css + artwork, <out>/themes/index.json,
//   <out>/themeable/loader.js + picker, <out>/root/ (favicons of the default pack).
//
//   node scripts/build.mjs [--packs packs] [--catalog catalog] [--out dist] [--default <id>|none]
import { copyFileSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { loadCatalog } from "../lib/catalog.mjs";
import { applyAliases, compilePack, listPacks, loadPack, validatePack } from "../lib/pack.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const args = parseArgs();
const packsDir = resolve(args.packs ?? join(root, "packs"));
const outDir = resolve(args.out ?? join(root, "dist"));
const defaultTheme = args.default ?? "none";
const catalog = loadCatalog(resolve(args.catalog ?? join(root, "catalog")));
// An image-derived catalog has no source to scan, so CSS references come from the committed one.
if (!catalog.cssReferences || !Object.keys(catalog.cssReferences).length) {
  catalog.cssReferences = loadCatalog(join(root, "catalog")).cssReferences ?? {};
}

const STOCK_SWATCH = { "--r-color-bg": "#07070f", "--r-color-brand-primary": "#8b74e8", "--r-color-brand-accent": "#e1a38d" };
const PLAIN_COLOR = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i;

function swatch(pack) {
  return Object.keys(STOCK_SWATCH).map((name) => {
    const value = pack.tokens?.dark?.[name] ?? pack.tokens?.common?.[name];
    return value && PLAIN_COLOR.test(value) ? value : STOCK_SWATCH[name];
  });
}

function copy(from, to) {
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
}

const ids = listPacks(packsDir);
if (defaultTheme !== "none" && !ids.includes(defaultTheme)) {
  fail(`--default ${defaultTheme} is not a pack in ${packsDir} (have: ${ids.join(", ") || "none"})`);
}

let failed = false;
const compiled = [];
for (const name of ids) {
  const loaded = loadPack(join(packsDir, name));
  const notes = applyAliases(loaded.pack, catalog.aliases);
  const { errors, warnings } = validatePack(loaded, catalog);
  if (loaded.pack.id !== name) errors.push(`id "${loaded.pack.id}" must match its folder name "${name}"`);
  for (const w of [...notes, ...warnings]) console.warn(`themeable: warning: packs/${name}: ${w}`);
  for (const e of errors) console.error(`themeable: error: packs/${name}: ${e}`);
  if (errors.length) {
    failed = true;
    continue;
  }
  compiled.push({ ...compilePack(loaded, catalog), swatch: swatch(loaded.pack) });
}
if (failed) fail("pack validation failed");

rmSync(outDir, { recursive: true, force: true });
for (const c of compiled) {
  const themeDir = join(outDir, "themes", c.meta.id);
  mkdirSync(themeDir, { recursive: true });
  writeFileSync(join(themeDir, "theme.css"), c.css);
  for (const f of c.files) copy(f.from, join(outDir, f.to));
  if (c.meta.id === defaultTheme) for (const f of c.rootFiles) copy(f.from, join(outDir, "root", f.to));
}

const manifest = {
  default: defaultTheme,
  themes: compiled.map((c) => ({ ...c.meta, swatch: c.swatch })),
};
mkdirSync(join(outDir, "themes"), { recursive: true });
writeFileSync(join(outDir, "themes", "index.json"), JSON.stringify(manifest, null, 2) + "\n");

const loader = readFileSync(join(root, "loader", "loader.js"), "utf8");
if (!loader.includes("__THEMEABLE_MANIFEST__")) fail("loader.js lost its manifest placeholder");
const embedded = JSON.stringify(manifest).replace(/</g, "\\u003c");
mkdirSync(join(outDir, "themeable"), { recursive: true });
writeFileSync(join(outDir, "themeable", "loader.js"), loader.replace("__THEMEABLE_MANIFEST__", embedded));
copy(join(root, "picker", "index.html"), join(outDir, "themeable", "index.html"));

console.log(
  `themeable: built ${compiled.length} pack(s) [${compiled.map((c) => c.meta.id).join(", ")}], default "${defaultTheme}" -> ${outDir}`,
);
