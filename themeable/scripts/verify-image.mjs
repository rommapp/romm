#!/usr/bin/env node
// Checks compiled packs against the CSS shipped in a RomM image, so a pack can't go stale silently.
import { join, resolve } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { buildTokenCatalog, readCss } from "../lib/catalog.mjs";
import { loadPack } from "../lib/pack.mjs";
import { findPacks, openPackFiles } from "../lib/packfiles.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const args = parseArgs();
if (!args.css) fail("pass --css <dir>");
const packsDir = resolve(args.packs ?? join(here, "..", "packs"));

const shipped = buildTokenCatalog(readCss(resolve(args.css)));
if (shipped.count === 0) fail(`no --r-* tokens in the image CSS at ${args.css}; upstream changed how tokens ship`);
const names = new Set(shipped.tokens.map((t) => t.name));

let missing = 0;
for (const found of findPacks(packsDir)) {
  const id = found.id;
  const files = openPackFiles(found);
  const { pack } = loadPack(files);
  files.close();
  for (const [scope, tokens] of Object.entries(pack.tokens ?? {})) {
    for (const name of Object.keys(tokens)) {
      if (!names.has(name)) {
        console.error(`themeable: packs/${id}: tokens.${scope}.${name} is not in this image's CSS`);
        missing++;
      }
    }
  }
}
if (missing) fail(`${missing} token(s) missing from the image`);
console.log(`themeable: image ships ${shipped.count} tokens; every pack token is present`);
