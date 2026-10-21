// Pack compilation shared by the image build, container start-up and Branding's Save changes.
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { CLIENT, RANDOM_ID, STOCK_ID, STOCK_SWATCH } from "./client.mjs";
import { applyAliases, compilePack, loadPack, validatePack, PACK_ID } from "./pack.mjs";
import { findPacks, openPackFiles, ZIP_EXT } from "./packfiles.mjs";

export { STOCK_ID } from "./client.mjs";
const PLAIN_COLOR = /^(#[0-9a-f]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))$/i;

export function swatch(pack) {
  return Object.keys(STOCK_SWATCH).map((name) => {
    const value = pack?.tokens?.dark?.[name] ?? pack?.tokens?.common?.[name];
    return value && PLAIN_COLOR.test(value) ? value : STOCK_SWATCH[name];
  });
}

function write(to, data) {
  mkdirSync(dirname(to), { recursive: true });
  writeFileSync(to, data);
}

function copy(from, to) {
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
}

/**
 * Finds the packs in each source folder in order, a later folder replacing a pack with the same id.
 * An archive carries a stamp (size, modification time, inode) so an unchanged one can be reused.
 */
export function collectPacks(sources) {
  const byName = new Map();
  for (const { dir, source } of sources) {
    for (const found of findPacks(dir)) {
      const warnings = found.shadowed
        ? [`the folder ${basename(found.shadowed)}/ is ignored because ${found.id}${ZIP_EXT} is installed; remove one of them`]
        : [];
      let stamp = null;
      if (found.format === "zip") {
        const st = statSync(found.path);
        // The inode changes when an archive is replaced by rename, even within the same millisecond.
        stamp = `${st.size}:${Math.floor(st.mtimeMs)}:${st.ino}`;
      }
      byName.set(found.id, { name: found.id, source, format: found.format, path: found.path, stamp, errors: [], warnings });
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

/** What a pack's compile left for the next one to reuse: its status and compiled metadata. */
function remember(status, c) {
  return { status: structuredClone(status), compiled: c ? { meta: c.meta, swatch: c.swatch, rootFiles: c.rootFiles.map((f) => ({ to: f.to })) } : null };
}

/**
 * Validates and compiles packs into outDir, returning the status the Branding tab shows.
 * `reuse` ({ key, dir, packs }) is the previous build: an archive whose stamp and compiler key
 * match is copied from `dir` instead of being opened again. The result's `cache` is the next `reuse.packs`.
 */
export function compileAll({ entries, catalog, outDir, selected = STOCK_ID, loaderSource, pickerFile, reuse = null }) {
  const compiled = [];
  const packs = [];
  const cache = {};
  for (const entry of entries) {
    const themeDir = join(outDir, "themes", entry.name);
    const key = entry.stamp && reuse?.key ? `${reuse.key}|${entry.source}|${entry.path}|${entry.stamp}` : null;
    const hit = key && reuse.packs?.[entry.name]?.key === key ? reuse.packs[entry.name] : null;
    const previousDir = hit?.compiled && join(reuse.dir, "themes", entry.name);
    if (hit && (!hit.compiled || existsSync(previousDir))) {
      packs.push(structuredClone(hit.status));
      if (hit.compiled) {
        cpSync(previousDir, themeDir, { recursive: true });
        compiled.push(hit.compiled);
      }
      cache[entry.name] = hit;
      continue;
    }

    let files = null;
    let loaded = null;
    const errors = [...entry.errors];
    try {
      files = openPackFiles(entry);
      loaded = loadPack(files);
    } catch (e) {
      errors.push(files ? `theme.json could not be read: ${e.message}` : `the archive could not be read: ${e.message}`);
    }
    const pack = loaded?.pack;
    const text = (v, fallback = "") => (typeof v === "string" ? v : fallback);
    const status = {
      id: entry.name,
      name: text(pack?.name, entry.name),
      description: text(pack?.description),
      author: text(pack?.author),
      version: text(pack?.version),
      source: entry.source,
      format: entry.format,
      swatch: swatch(pack),
      valid: false,
      errors,
      warnings: [...entry.warnings],
    };
    packs.push(status);
    let c = null;
    // A malformed pack must only ever disable itself, never the other packs.
    if (loaded) {
      try {
        status.warnings.push(...applyAliases(pack, catalog.aliases));
        const checked = validatePack(loaded, catalog);
        if (pack.id !== entry.name) {
          const where = entry.format === "zip" ? `file name "${entry.name}${ZIP_EXT}"` : `folder name "${entry.name}"`;
          checked.errors.push(`id "${pack.id}" must match its ${where}`);
        }
        status.errors.push(...checked.errors);
        status.warnings.push(...checked.warnings);
        if (!status.errors.length) {
          c = { ...compilePack(loaded, catalog), swatch: status.swatch };
          write(join(themeDir, "theme.css"), c.css);
          for (const f of c.files) write(join(outDir, f.to), files.read(f.path));
          // Every pack's favicons, so Branding can preview them for packs that aren't selected.
          for (const f of c.rootFiles) write(join(themeDir, "root", f.to), files.read(f.path));
          compiled.push(c);
          status.valid = true;
        }
      } catch (e) {
        c = null;
        status.errors.push(`could not be compiled: ${e.message}`);
        rmSync(themeDir, { recursive: true, force: true });
      }
    }
    files?.close();
    if (key) cache[entry.name] = { key, ...remember(status, c) };
  }

  let effective = selected;
  let reason = null;
  if (selected === RANDOM_ID) {
    if (!compiled.length) {
      reason = "Random has no usable packs to choose from, so RomM's default look is in use";
      effective = STOCK_ID;
    }
  } else if (selected !== STOCK_ID && !compiled.some((c) => c.meta.id === selected)) {
    const known = packs.find((p) => p.id === selected);
    reason = known ? `"${selected}" has errors, so RomM's default look is in use` : `"${selected}" is not installed, so RomM's default look is in use`;
    effective = STOCK_ID;
  }

  const active = compiled.find((c) => c.meta.id === effective);
  try {
    for (const f of active?.rootFiles ?? []) copy(join(outDir, "themes", effective, "root", f.to), join(outDir, "themeable", "root", f.to));
  } catch (e) {
    rmSync(join(outDir, "themeable", "root"), { recursive: true, force: true });
    packs.find((p) => p.id === effective)?.warnings.push(`favicons could not be copied, so RomM's own are used: ${e.message}`);
  }

  const manifest = { default: effective, client: CLIENT, themes: compiled.map((c) => ({ ...c.meta, swatch: c.swatch })) };
  mkdirSync(join(outDir, "themes"), { recursive: true });
  writeFileSync(join(outDir, "themes", "index.json"), JSON.stringify(manifest, null, 2) + "\n");

  if (!loaderSource.includes("__THEMEABLE_MANIFEST__")) throw new Error("loader.js lost its manifest placeholder");
  const embedded = JSON.stringify(manifest).replace(/</g, "\\u003c");
  mkdirSync(join(outDir, "themeable"), { recursive: true });
  writeFileSync(join(outDir, "themeable", "loader.js"), loaderSource.replace("__THEMEABLE_MANIFEST__", embedded));
  copy(pickerFile, join(outDir, "themeable", "index.html"));

  return { selected, effective, reason, packs, compiled, cache, client: CLIENT };
}
