#!/usr/bin/env node
// Regenerates docs/theme.example.json from the catalog and upstream's Vuetify theme;
// --check exits 1 when the committed file is out of date instead of writing it.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { buildExample, parseThemeColor, parseVuetifyThemes } from "../lib/example.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const args = parseArgs();
const frontend = resolve(args.frontend ?? join(root, "../frontend"));
const out = join(root, "docs/theme.example.json");
const readJson = (file) => JSON.parse(readFileSync(join(root, "catalog", file), "utf8"));

const text =
  JSON.stringify(
    buildExample({
      tokenCatalog: readJson("tokens.json"),
      assetCatalog: readJson("assets.json"),
      vuetify: parseVuetifyThemes(readFileSync(join(frontend, "src/styles/themes.ts"), "utf8")),
      themeColor: parseThemeColor(readFileSync(join(frontend, "index.html"), "utf8")),
    }),
    null,
    2,
  ) + "\n";

if (args.check) {
  let current = "";
  try {
    current = readFileSync(out, "utf8");
  } catch {
    // A missing file is out of date too.
  }
  if (current !== text) fail("docs/theme.example.json is out of date; run `npm run example`");
  console.log("themeable: docs/theme.example.json is up to date");
} else {
  writeFileSync(out, text);
  console.log(`themeable: wrote docs/theme.example.json`);
}
