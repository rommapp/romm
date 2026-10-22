// Pack compilation shared by the image build, container start-up and Branding's Save changes.
import { copyFileSync, cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { ACCESSIBILITY_TAG, CLIENT, RANDOM_ID, STOCK_ID, STOCK_SWATCH } from "./client.mjs";
import { applyAliases, badPackName, compilePack, loadPack, validatePack, PACK_ID } from "./pack.mjs";
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
 * A source can `exclude` ids, add `standIns` ({ id, format, path }) that replace or add a pack for
 * one compile, and take `archivesOnly`, which skips folder packs. An archive carries a stamp (size, modification time, inode) so an unchanged one can be
 * reused; a stand-in never is.
 */
export function collectPacks(sources) {
  const byName = new Map();
  for (const { dir, source, exclude = [], standIns = [], archivesOnly = false } of sources) {
    for (const standIn of standIns) {
      byName.set(standIn.id, { name: standIn.id, source, format: standIn.format, path: standIn.path, stamp: null, errors: [], warnings: [] });
    }
    for (const found of findPacks(dir).filter((p) => !exclude.includes(p.id) && !standIns.some((s) => s.id === p.id))) {
      if (archivesOnly && found.format !== "zip") continue;
      const warnings = found.shadowed && !archivesOnly
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

// Which groups Random draws from until an admin changes them. Packs in the themes folder
// without the accessibility tag are always in the draw.
export const RANDOM_POOL_DEFAULTS = Object.freeze({ stock: false, built_in: true, accessibility: true });

/** Random's groups from saved settings, each a boolean, with defaults for anything missing. */
export function readRandomPool(value) {
  const out = { ...RANDOM_POOL_DEFAULTS };
  for (const key of Object.keys(RANDOM_POOL_DEFAULTS)) {
    if (typeof value?.[key] === "boolean") out[key] = value[key];
  }
  return out;
}

// A pack's group, which sets its place in every list and which of Random's switches covers it.
export const PACK_GROUPS = ["accessibility", "built-in", "folder"];
export function packGroup(source, tags) {
  if (tags?.includes(ACCESSIBILITY_TAG)) return "accessibility";
  return source === "built-in" ? "built-in" : "folder";
}
const packRank = (source, tags) => PACK_GROUPS.indexOf(packGroup(source, tags));
// Random's switch for each group; packs in the themes folder are always in the draw.
const GROUP_SWITCH = { accessibility: "accessibility", "built-in": "built_in", folder: null };

/**
 * Reads themeable.json: the server's theme, the built-in packs hidden by Delete, Random's groups
 * and the names given to built-in packs. Anything unreadable falls back to RomM's own look with nothing hidden.
 */
export function readSelection(settingsFile) {
  const fallback = { theme: STOCK_ID, hidden: [], random: readRandomPool(null), names: {} };
  if (!settingsFile || !existsSync(settingsFile)) return { ...fallback, note: null };
  try {
    const saved = JSON.parse(readFileSync(settingsFile, "utf8"));
    const theme = saved?.theme;
    const hidden = Array.isArray(saved?.hidden) ? saved.hidden.filter((id) => typeof id === "string" && PACK_ID.test(id)) : [];
    const random = readRandomPool(saved?.random);
    const names = Object.fromEntries(
      Object.entries(saved?.names && typeof saved.names === "object" ? saved.names : {}).filter(([id, name]) => PACK_ID.test(id) && !badPackName(name)),
    );
    if (theme === STOCK_ID || (typeof theme === "string" && PACK_ID.test(theme))) return { theme, hidden, random, names, note: null };
    return { theme: STOCK_ID, hidden, random, names, note: `${settingsFile} has no valid "theme"; using RomM's default look` };
  } catch (e) {
    return { ...fallback, note: `${settingsFile} could not be read (${e.message}); using RomM's default look` };
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
export function compileAll({ entries, catalog, outDir, selected = STOCK_ID, randomPool = null, names = {}, loaderSource, pickerFile, reuse = null }) {
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
        compiled.push({ ...hit.compiled, source: entry.source });
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
      tags: Array.isArray(pack?.tags) ? pack.tags.filter((t) => typeof t === "string") : [],
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
          c = { ...compilePack(loaded, catalog), swatch: status.swatch, source: entry.source };
          write(join(themeDir, "theme.css"), c.css);
          for (const f of c.files) write(join(outDir, f.to), files.read(f.path));
          // Every pack's favicons, so Branding can preview them for packs that aren't selected.
          for (const f of c.rootFiles) write(join(themeDir, "root", f.to), files.read(f.path));
          compiled.push(c);
          status.cover = c.meta.cover;
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

  // A built-in pack renamed in Branding shows its new name everywhere, and keeps its own for Reset.
  for (const status of packs) {
    if (status.source !== "built-in" || !names[status.id]) continue;
    status.default_name = status.name;
    status.name = names[status.id];
  }
  for (let i = 0; i < compiled.length; i++) {
    const renamed = compiled[i].source === "built-in" && names[compiled[i].meta.id];
    if (renamed) compiled[i] = { ...compiled[i], meta: { ...compiled[i].meta, name: renamed } };
  }

  const byRank = (a, b) => packRank(a.source, a.tags) - packRank(b.source, b.tags) || a.id.localeCompare(b.id);
  packs.sort(byRank);
  compiled.sort((a, b) => byRank({ ...a.meta, source: a.source }, { ...b.meta, source: b.source }));

  // The exact ids Random may draw, resolved once here so the loader, picker and Branding agree.
  const pool = readRandomPool(randomPool);
  const draw = compiled
    .filter((c) => {
      const toggle = GROUP_SWITCH[packGroup(c.source, c.meta.tags)];
      return toggle === null || pool[toggle];
    })
    .map((c) => c.meta.id);
  // The ids each switch covers, so Branding can count the draw live before saving.
  const members = { built_in: [], accessibility: [], always: [] };
  for (const c of compiled) members[GROUP_SWITCH[packGroup(c.source, c.meta.tags)] ?? "always"].push(c.meta.id);
  if (pool.stock) draw.unshift(STOCK_ID);
  const random = { ...pool, ids: draw, members };

  let effective = selected;
  let reason = null;
  if (selected === RANDOM_ID) {
    if (!draw.length) {
      reason = "Random has nothing to draw from in the groups it includes, so RomM's default look is in use";
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

  const manifest = { default: effective, client: CLIENT, random, themes: compiled.map((c) => ({ ...c.meta, swatch: c.swatch, source: c.source })) };
  mkdirSync(join(outDir, "themes"), { recursive: true });
  writeFileSync(join(outDir, "themes", "index.json"), JSON.stringify(manifest, null, 2) + "\n");

  if (!loaderSource.includes("__THEMEABLE_MANIFEST__")) throw new Error("loader.js lost its manifest placeholder");
  const embedded = JSON.stringify(manifest).replace(/</g, "\\u003c");
  mkdirSync(join(outDir, "themeable"), { recursive: true });
  writeFileSync(join(outDir, "themeable", "loader.js"), loaderSource.replace("__THEMEABLE_MANIFEST__", embedded));
  copy(pickerFile, join(outDir, "themeable", "index.html"));

  return { selected, effective, reason, packs, compiled, cache, random, client: CLIENT };
}
