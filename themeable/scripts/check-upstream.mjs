#!/usr/bin/env node
// Compares the committed catalog with the current upstream tree and checks the module's anchors;
// exits 1 when a pack or a hook would break.
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "../lib/args.mjs";
import { buildAssetCatalog, buildTokenCatalog, diffCatalogs, loadCatalog, readCss } from "../lib/catalog.mjs";
import { findAssetsBlock } from "../lib/nginx.mjs";
import { applyAliases, loadPack, validatePack } from "../lib/pack.mjs";
import { findPacks, openPackFiles } from "../lib/packfiles.mjs";
import { loadPatches, overlayFiles } from "../lib/source.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const args = parseArgs();
const upstream = resolve(args.upstream ?? join(root, ".."));
const fe = join(upstream, "frontend");

const readJson = (f) => (existsSync(f) ? JSON.parse(readFileSync(f, "utf8")) : {});
const oldCat = {
  tokens: readJson(join(root, "catalog/tokens.json")),
  assets: readJson(join(root, "catalog/assets.json")),
};
const newCat = {
  tokens: buildTokenCatalog(readCss(join(fe, "src/v2/styles/tokens.css"))),
  assets: buildAssetCatalog({ dir: join(fe, "assets"), srcDir: join(fe, "src") }),
};
const diff = diffCatalogs(oldCat, newCat);

const problems = [];
const notes = [];

// Anchors the hooks depend on.
const anchors = [
  ["frontend/index.html has </head>", () => readFileSync(join(fe, "index.html"), "utf8").includes("</head>")],
  ["RomM.vue toggles r-v2-dark/r-v2-light on <html>", () => {
    const vue = readFileSync(join(fe, "src/RomM.vue"), "utf8");
    return vue.includes('"r-v2-dark"') && vue.includes('"r-v2-light"') && vue.includes("documentElement");
  }],
  ["tokens.css still has dark and light scopes", () => {
    const scopes = newCat.tokens.tokens.flatMap((t) => Object.keys(t.defaults));
    return scopes.includes("dark") && scopes.includes("light");
  }],
  ["nginx template has a single `location /assets` block", () => {
    findAssetsBlock(readFileSync(join(upstream, "docker/nginx/templates/default.conf.template"), "utf8"));
    return true;
  }],
];
for (const [label, test] of anchors) {
  let ok = false;
  let reason = "";
  try {
    ok = test();
  } catch (e) {
    reason = ` (${e.message})`;
  }
  if (!ok) problems.push(`Anchor missing: ${label}${reason}`);
}

// Patches still apply, and overlay files don't collide with new upstream files.
for (const patch of await loadPatches(join(root, "patches"))) {
  const target = join(upstream, patch.file);
  if (!existsSync(target)) {
    problems.push(`Patch ${patch.name}: ${patch.file} no longer exists upstream`);
    continue;
  }
  try {
    patch.apply(readFileSync(target, "utf8"));
  } catch (e) {
    problems.push(`Patch ${patch.name} (${patch.description}) no longer applies: ${e.message}`);
  }
}
for (const rel of overlayFiles(join(root, "overlay"))) {
  if (existsSync(join(upstream, rel))) problems.push(`Overlay file ${rel} now exists upstream; rename it or turn it into a patch`);
}

// Every pack against the new catalog.
const catalog = loadCatalog(join(root, "catalog"));
catalog.tokens = new Set(newCat.tokens.tokens.map((t) => t.name));
catalog.assets = new Set(newCat.assets.files);
for (const found of findPacks(join(root, "packs"))) {
  const id = found.id;
  const loaded = loadPack(openPackFiles(found));
  notes.push(...applyAliases(loaded.pack, catalog.aliases).map((w) => `packs/${id}: ${w}`));
  const { errors, warnings } = validatePack(loaded, catalog);
  problems.push(...errors.map((e) => `packs/${id}: ${e}`));
  notes.push(...warnings.map((w) => `packs/${id}: ${w}`));
  loaded.files.close();
}

const section = (title, items) => (items.length ? `### ${title} (${items.length})\n\n${items.map((i) => `- \`${i}\``).join("\n")}\n` : "");
const report = [
  "## themeable upstream check",
  problems.length ? `**${problems.length} problem(s) need fixing before release.**` : "**No breaking changes for the theme module.**",
  problems.length ? `### Problems\n\n${problems.map((p) => `- ${p}`).join("\n")}\n` : "",
  section("Tokens added", diff.tokensAdded),
  section("Tokens removed (add renames to catalog/token-aliases.json)", diff.tokensRemoved),
  section("Token defaults changed", diff.tokenDefaultsChanged),
  section("Asset slots added", diff.assetsAdded),
  section("Asset slots removed", diff.assetsRemoved),
  notes.length ? `### Notes\n\n${notes.map((n) => `- ${n}`).join("\n")}\n` : "",
  problems.length ? "Fix the problems, then run `npm run catalog` to accept the new catalog." : "",
].filter(Boolean).join("\n\n");

const reportFile = args.report ? resolve(args.report) : join(mkdtempSync(join(tmpdir(), "themeable-")), "report.md");
writeFileSync(reportFile, report + "\n");
console.log(report);
process.exit(problems.length ? 1 : 0);
