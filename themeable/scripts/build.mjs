#!/usr/bin/env node
// Compiles every pack in packs/ into a web root fragment; fails on any invalid pack.
import { readFileSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { loadCatalog } from "../lib/catalog.mjs";
import { collectPacks, compileAll, STOCK_ID } from "../lib/compile.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const args = parseArgs();
const packsDir = resolve(args.packs ?? join(root, "packs"));
const outDir = resolve(args.out ?? join(root, "dist"));
const defaultTheme = args.default ?? STOCK_ID;
const catalog = loadCatalog(resolve(args.catalog ?? join(root, "catalog")));
// An image-derived catalog has no source to scan, so CSS references come from the committed one.
if (!catalog.cssReferences || !Object.keys(catalog.cssReferences).length) {
  catalog.cssReferences = loadCatalog(join(root, "catalog")).cssReferences ?? {};
}

const entries = collectPacks([{ dir: packsDir, source: "built-in" }]);
if (defaultTheme !== STOCK_ID && !entries.some((e) => e.name === defaultTheme)) {
  fail(`--default ${defaultTheme} is not a pack in ${packsDir} (have: ${entries.map((e) => e.name).join(", ") || "none"})`);
}

rmSync(outDir, { recursive: true, force: true });
const result = compileAll({
  entries,
  catalog,
  outDir,
  selected: defaultTheme,
  loaderSource: readFileSync(join(root, "loader", "loader.js"), "utf8"),
  pickerFile: join(root, "picker", "index.html"),
});

for (const p of result.packs) {
  for (const w of p.warnings) console.warn(`themeable: warning: packs/${p.id}: ${w}`);
  for (const e of p.errors) console.error(`themeable: error: packs/${p.id}: ${e}`);
}
if (result.packs.some((p) => !p.valid)) fail("pack validation failed");

console.log(
  `themeable: built ${result.compiled.length} pack(s) [${result.compiled.map((c) => c.meta.id).join(", ")}], default "${result.effective}" -> ${outDir}`,
);
