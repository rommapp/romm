// Builds the token and asset catalogs that packs are validated against.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative, sep } from "node:path";
import { scanCssReferences } from "./cssrefs.mjs";
import { EXCLUDED_ASSET_DIRS } from "./pack.mjs";
import { SCOPES, allTokenNames, parseTokenCss, tokenGroup } from "./tokens.mjs";

const ART_EXT = new Set([
  ".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".avif",
  ".woff", ".woff2", ".ttf", ".otf", ".css",
]);

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.isFile() || entry.isSymbolicLink()) out.push(full);
  }
  return out;
}

/** Reads CSS from a file, or every top-level .css file in a directory (a built image's /assets). */
export function readCss(path) {
  if (statSync(path).isDirectory()) {
    return readdirSync(path)
      .filter((f) => f.endsWith(".css"))
      .sort()
      .map((f) => readFileSync(join(path, f), "utf8"))
      .join("\n");
  }
  return readFileSync(path, "utf8");
}

export function buildTokenCatalog(cssText) {
  const scopes = parseTokenCss(cssText);
  const tokens = allTokenNames(scopes).map((name) => ({
    name,
    group: tokenGroup(name),
    defaults: Object.fromEntries(SCOPES.filter((s) => name in scopes[s]).map((s) => [s, scopes[s][name]])),
  }));
  return { count: tokens.length, tokens };
}

export function isThemeableAsset(rel) {
  const top = rel.split("/")[0];
  return !EXCLUDED_ASSET_DIRS.includes(top) && ART_EXT.has(extname(rel).toLowerCase());
}

/** Asset paths ("/assets/...") from a directory tree or from a newline-separated list. */
export function listAssets({ dir, listFile }) {
  let rels;
  if (listFile) {
    rels = readFileSync(listFile, "utf8")
      .split("\n")
      .map((l) => l.trim().replace(/^\.?\/?(assets\/)?/, ""))
      .filter(Boolean);
  } else {
    rels = walk(dir).map((f) => relative(dir, f).split(sep).join("/"));
  }
  return [...new Set(rels.filter(isThemeableAsset).map((r) => `/assets/${r}`))].sort();
}

/** Counts literal /assets/ references in app source, plus template-string prefixes. */
export function scanReferences(srcDir) {
  const references = {};
  const prefixes = new Set();
  if (!srcDir || !existsSync(srcDir)) return { references, dynamicPrefixes: [] };
  const literal = /\/assets\/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+/g;
  const dynamic = /\/assets\/((?:[A-Za-z0-9_-]+\/)+)\$\{/g;
  for (const file of walk(srcDir)) {
    if (!/\.(vue|ts|js|css)$/.test(file) || /\.(test|stories|fixtures)\./.test(file)) continue;
    const text = readFileSync(file, "utf8");
    for (const m of text.match(literal) ?? []) references[m] = (references[m] ?? 0) + 1;
    for (const m of text.matchAll(dynamic)) prefixes.add(`/assets/${m[1]}`);
  }
  const sorted = Object.fromEntries(Object.entries(references).sort(([a], [b]) => a.localeCompare(b)));
  return { references: sorted, dynamicPrefixes: [...prefixes].sort() };
}

export function buildAssetCatalog({ dir, listFile, srcDir }) {
  const files = listAssets({ dir, listFile });
  const { references, dynamicPrefixes } = scanReferences(srcDir);
  const cssReferences = srcDir && existsSync(srcDir) ? scanCssReferences(srcDir) : {};
  return { count: files.length, files, references, dynamicPrefixes, cssReferences };
}

/** Loads a catalog directory into the Sets validatePack expects. */
export function loadCatalog(catalogDir) {
  const out = {};
  const tokensFile = join(catalogDir, "tokens.json");
  const assetsFile = join(catalogDir, "assets.json");
  if (existsSync(tokensFile)) {
    out.tokens = new Set(JSON.parse(readFileSync(tokensFile, "utf8")).tokens.map((t) => t.name));
  }
  if (existsSync(assetsFile)) {
    const assets = JSON.parse(readFileSync(assetsFile, "utf8"));
    out.assets = new Set(assets.files);
    out.cssReferences = assets.cssReferences ?? {};
  }
  const aliasesFile = join(catalogDir, "token-aliases.json");
  out.aliases = existsSync(aliasesFile) ? JSON.parse(readFileSync(aliasesFile, "utf8")) : {};
  return out;
}

/** Differences between two catalogs, as plain lists. */
export function diffCatalogs(oldCat, newCat) {
  const names = (c) => new Set((c.tokens?.tokens ?? []).map((t) => t.name));
  const oldT = names(oldCat);
  const newT = names(newCat);
  const oldA = new Set(oldCat.assets?.files ?? []);
  const newA = new Set(newCat.assets?.files ?? []);
  const changedDefaults = [];
  const oldByName = new Map((oldCat.tokens?.tokens ?? []).map((t) => [t.name, t]));
  for (const t of newCat.tokens?.tokens ?? []) {
    const prev = oldByName.get(t.name);
    if (prev && JSON.stringify(prev.defaults) !== JSON.stringify(t.defaults)) changedDefaults.push(t.name);
  }
  return {
    tokensAdded: [...newT].filter((n) => !oldT.has(n)),
    tokensRemoved: [...oldT].filter((n) => !newT.has(n)),
    tokenDefaultsChanged: changedDefaults,
    assetsAdded: [...newA].filter((n) => !oldA.has(n)),
    assetsRemoved: [...oldA].filter((n) => !newA.has(n)),
  };
}
