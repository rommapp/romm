#!/usr/bin/env node
// Regenerates catalog/tokens.json and catalog/assets.json from an upstream RomM tree or image.
//
//   node scripts/catalog.mjs                                   # from this repo's frontend/
//   node scripts/catalog.mjs --tokens <css file|dir> --assets-list <file> --out <dir>
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { buildAssetCatalog, buildTokenCatalog, readCss } from "../lib/catalog.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const frontend = resolve(root, "../frontend");
const args = parseArgs();

const tokensPath = resolve(args.tokens ?? join(frontend, "src/v2/styles/tokens.css"));
const outDir = resolve(args.out ?? join(root, "catalog"));

const tokenCatalog = buildTokenCatalog(readCss(tokensPath));
if (tokenCatalog.count === 0) fail(`no --r-* tokens found in ${tokensPath}; did upstream change its token scopes?`);

const assetCatalog = buildAssetCatalog({
  dir: args["assets-list"] ? undefined : resolve(args["assets-dir"] ?? join(frontend, "assets")),
  listFile: args["assets-list"] ? resolve(args["assets-list"]) : undefined,
  srcDir: args["no-src"] ? undefined : resolve(args.src ?? join(frontend, "src")),
});

// An image has no source to scan for CSS rules, so they can be carried over from a committed catalog.
if (args["css-refs-from"]) {
  assetCatalog.cssReferences = JSON.parse(readFileSync(resolve(args["css-refs-from"]), "utf8")).cssReferences ?? {};
}

mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "tokens.json"), JSON.stringify(tokenCatalog, null, 2) + "\n");
writeFileSync(join(outDir, "assets.json"), JSON.stringify(assetCatalog, null, 2) + "\n");
console.log(`themeable: catalog has ${tokenCatalog.count} tokens and ${assetCatalog.count} asset slots -> ${outDir}`);
