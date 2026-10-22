// Pack files behind one interface, so validation and compiling read a .zip and a folder the same way:
// { format, list(), exists(path), read(path), close() } with paths relative to the pack root.
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { basename, join, posix, resolve, sep } from "node:path";
import { openZip, writeZip } from "./zip.mjs";

export const ZIP_EXT = ".zip";
// Holds folder packs after Convert; a dot keeps it out of the pack list.
export const CONVERTED_DIR = ".converted";
// Added by macOS's Compress and Finder, never part of a pack.
const ARCHIVE_NOISE = /(^|\/)(__MACOSX\/|\.DS_Store$)/;

/** A path inside the pack in plain "a/b.svg" form, or null if it would leave the pack. */
export function packPath(rel) {
  if (typeof rel !== "string" || !rel || rel.includes("\\") || rel.includes("\0")) return null;
  const norm = posix.normalize(rel);
  if (posix.isAbsolute(norm) || norm === "." || norm === ".." || norm.startsWith("../")) return null;
  return norm;
}

export function folderFiles(dir) {
  const root = resolve(dir);
  const full = (rel) => {
    const p = packPath(rel);
    if (!p) return null;
    const f = resolve(root, p);
    return f.startsWith(root + sep) ? f : null;
  };
  const walk = (d, prefix) =>
    readdirSync(d, { withFileTypes: true }).flatMap((e) =>
      e.isDirectory() ? walk(join(d, e.name), `${prefix}${e.name}/`) : e.isFile() ? [`${prefix}${e.name}`] : [],
    );
  return {
    format: "folder",
    list: () => walk(root, ""),
    exists: (rel) => {
      const f = full(rel);
      return !!f && existsSync(f) && statSync(f).isFile();
    },
    read: (rel) => {
      const f = full(rel);
      if (!f) throw new Error(`${rel} is outside the pack`);
      return readFileSync(f);
    },
    close: () => {},
  };
}

/** The folder theme.json sits in ("" for the root) among an archive's entry names. */
function packRoot(names) {
  if (names.includes("theme.json")) return "";
  const tops = new Set(names.map((n) => (n.includes("/") ? n.slice(0, n.indexOf("/") + 1) : "")));
  const [only] = tops;
  if (tops.size !== 1 || !only || !names.includes(`${only}theme.json`)) {
    throw new Error("theme.json must be at the archive's root or inside its one top-level folder");
  }
  return only;
}

/** Opens a pack archive; theme.json sits at its root or inside its one top-level folder. */
export function zipFiles(file, limits) {
  const zip = openZip(file, limits);
  try {
    const names = zip.names.filter((n) => !ARCHIVE_NOISE.test(n));
    const prefix = packRoot(names);
    const files = new Set(names.filter((n) => n.startsWith(prefix)).map((n) => n.slice(prefix.length)));
    const cache = new Map();
    return {
      format: "zip",
      list: () => [...files],
      exists: (rel) => files.has(packPath(rel)),
      read: (rel) => {
        const p = packPath(rel);
        if (!files.has(p)) throw new Error(`${rel} is not in the archive`);
        if (!cache.has(p)) cache.set(p, zip.read(prefix + p));
        return cache.get(p);
      },
      close: () => zip.close(),
    };
  } catch (e) {
    zip.close();
    throw e;
  }
}

/**
 * Lists the packs in a folder: each <id>.zip, and each <id>/ folder holding a theme.json.
 * Returns [{ id, format, path, shadowed }]; a folder beside an archive of the same id is `shadowed`.
 */
export function findPacks(dir) {
  if (!dir || !existsSync(dir)) return [];
  const found = new Map();
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith(".")) continue;
    if (e.isFile() && e.name.toLowerCase().endsWith(ZIP_EXT)) {
      const id = basename(e.name, e.name.slice(-ZIP_EXT.length));
      const previous = found.get(id);
      found.set(id, { id, format: "zip", path: join(dir, e.name), shadowed: previous?.format === "folder" ? previous.path : null });
    } else if (e.isDirectory() && existsSync(join(dir, e.name, "theme.json"))) {
      const zipped = found.get(e.name);
      if (zipped) zipped.shadowed = join(dir, e.name);
      else found.set(e.name, { id: e.name, format: "folder", path: join(dir, e.name), shadowed: null });
    }
  }
  return [...found.values()].sort((a, b) => a.id.localeCompare(b.id));
}

export function openPackFiles({ format, path }, limits) {
  return format === "zip" ? zipFiles(path, limits) : folderFiles(path);
}

/** Writes a folder pack's files, in a stable order, to an archive with theme.json at its root. */
export function zipFolderPack(dir, file) {
  const files = folderFiles(dir);
  writeZip(file, files.list().sort().map((name) => ({ name, data: files.read(name) })));
}

/** Writes a copy of a pack archive with its theme.json passed through `update(pack)`. */
export function rewriteZipPack(file, outFile, update) {
  const zip = openZip(file);
  try {
    const names = zip.names.filter((n) => !ARCHIVE_NOISE.test(n));
    const themeJson = `${packRoot(names)}theme.json`;
    const pack = update(JSON.parse(zip.read(themeJson).toString("utf8")));
    writeZip(
      outFile,
      names.map((name) => ({ name, data: name === themeJson ? Buffer.from(JSON.stringify(pack, null, 2) + "\n") : zip.read(name) })),
    );
  } finally {
    zip.close();
  }
}
