// Shared pack compilation for the image build, the container start-up step and
// the Branding tab's Save changes. Writes a web root fragment:
//   themes/<id>/theme.css + artwork, themes/index.json,
//   themeable/loader.js + picker, themeable/root/ (favicons of the selected pack).
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { applyAliases, compilePack, listPacks, loadPack, validatePack, PACK_ID } from "./pack.mjs";

export const STOCK_ID = "none";
const STOCK_SWATCH = { "--r-color-bg": "#07070f", "--r-color-brand-primary": "#8b74e8", "--r-color-brand-accent": "#e1a38d" };
const PLAIN_COLOR = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i;

export function swatch(pack) {
  return Object.keys(STOCK_SWATCH).map((name) => {
    const value = pack?.tokens?.dark?.[name] ?? pack?.tokens?.common?.[name];
    return value && PLAIN_COLOR.test(value) ? value : STOCK_SWATCH[name];
  });
}

export const STOCK_SWATCH_VALUES = Object.values(STOCK_SWATCH);

function copy(from, to) {
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
}

/**
 * Loads packs from each source in order; a later source replaces an earlier pack with
 * the same folder name. Returns [{ name, dir, source, loaded?, errors, warnings }].
 */
export function collectPacks(sources) {
  const byName = new Map();
  for (const { dir, source } of sources) {
    if (!dir || !existsSync(dir)) continue;
    for (const name of listPacks(dir)) {
      const entry = { name, dir: join(dir, name), source, errors: [], warnings: [] };
      try {
        entry.loaded = loadPack(entry.dir);
      } catch (e) {
        entry.errors.push(`theme.json could not be read: ${e.message}`);
      }
      byName.set(name, entry);
    }
  }
  return [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Reads the saved selection; anything unreadable falls back to RomM's own look. */
export function readSelection(settingsFile) {
  if (!settingsFile || !existsSync(settingsFile)) return { theme: STOCK_ID, note: null };
  try {
    const theme = JSON.parse(readFileSync(settingsFile, "utf8"))?.theme;
    if (theme === STOCK_ID || (typeof theme === "string" && PACK_ID.test(theme))) return { theme, note: null };
    return { theme: STOCK_ID, note: `${settingsFile} has no valid "theme"; using RomM's default look` };
  } catch (e) {
    return { theme: STOCK_ID, note: `${settingsFile} could not be read (${e.message}); using RomM's default look` };
  }
}

/**
 * Validates and compiles packs into outDir.
 * Returns the status the Branding tab shows: every pack with its errors, and which theme is in effect.
 */
export function compileAll({ entries, catalog, outDir, selected = STOCK_ID, loaderSource, pickerFile }) {
  const compiled = [];
  const packs = [];
  for (const entry of entries) {
    const status = {
      id: entry.loaded?.pack?.id ?? entry.name,
      name: entry.loaded?.pack?.name ?? entry.name,
      description: entry.loaded?.pack?.description ?? "",
      author: entry.loaded?.pack?.author ?? "",
      version: entry.loaded?.pack?.version ?? "",
      source: entry.source,
      swatch: swatch(entry.loaded?.pack),
      valid: false,
      errors: [...entry.errors],
      warnings: [...entry.warnings],
    };
    if (entry.loaded) {
      status.warnings.push(...applyAliases(entry.loaded.pack, catalog.aliases));
      const { errors, warnings } = validatePack(entry.loaded, catalog);
      if (entry.loaded.pack.id !== entry.name) errors.push(`id "${entry.loaded.pack.id}" must match its folder name "${entry.name}"`);
      status.errors.push(...errors);
      status.warnings.push(...warnings);
      if (!status.errors.length) {
        try {
          compiled.push({ ...compilePack(entry.loaded, catalog), swatch: status.swatch });
          status.valid = true;
        } catch (e) {
          status.errors.push(`compile failed: ${e.message}`);
        }
      }
    }
    packs.push(status);
  }

  let effective = selected;
  let reason = null;
  if (selected !== STOCK_ID && !compiled.some((c) => c.meta.id === selected)) {
    const known = packs.find((p) => p.id === selected);
    reason = known ? `"${selected}" has errors, so RomM's default look is in use` : `"${selected}" is not installed, so RomM's default look is in use`;
    effective = STOCK_ID;
  }

  for (const c of compiled) {
    const themeDir = join(outDir, "themes", c.meta.id);
    mkdirSync(themeDir, { recursive: true });
    writeFileSync(join(themeDir, "theme.css"), c.css);
    for (const f of c.files) copy(f.from, join(outDir, f.to));
    if (c.meta.id === effective) for (const f of c.rootFiles) copy(f.from, join(outDir, "themeable", "root", f.to));
  }

  const manifest = { default: effective, themes: compiled.map((c) => ({ ...c.meta, swatch: c.swatch })) };
  mkdirSync(join(outDir, "themes"), { recursive: true });
  writeFileSync(join(outDir, "themes", "index.json"), JSON.stringify(manifest, null, 2) + "\n");

  if (!loaderSource.includes("__THEMEABLE_MANIFEST__")) throw new Error("loader.js lost its manifest placeholder");
  const embedded = JSON.stringify(manifest).replace(/</g, "\\u003c");
  mkdirSync(join(outDir, "themeable"), { recursive: true });
  writeFileSync(join(outDir, "themeable", "loader.js"), loaderSource.replace("__THEMEABLE_MANIFEST__", embedded));
  copy(pickerFile, join(outDir, "themeable", "index.html"));

  return { selected, effective, reason, packs, compiled };
}
