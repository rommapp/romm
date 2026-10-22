// Changes to the themes folder made from Branding: select, install (upload), rename, reset a
// built-in's name, delete and restore. Each one is staged as stand-in packs and new settings that one compile tries; the
// themes folder only changes in install(), once that build is live, so a failure changes nothing.
import { copyFileSync, existsSync, mkdirSync, renameSync, rmSync, unlinkSync } from "node:fs";
import { basename, join } from "node:path";
import { RANDOM_ID, STOCK_ID } from "./client.mjs";
import { RANDOM_POOL_DEFAULTS } from "./compile.mjs";
import { applyAliases, badPackName, loadPack, PACK_ID, RESERVED_IDS, validatePack } from "./pack.mjs";
import { CONVERTED_DIR, findPacks, rewriteZipPack, zipFiles, zipFolderPack, ZIP_EXT } from "./packfiles.mjs";

/** A request turned down before anything changed; it isn't recorded in status.json. */
export class Refusal extends Error {}

/**
 * Checks an uploaded archive exactly as a compile would, without touching the themes folder.
 * Returns { id, name, errors, warnings, existing } where `existing` is how the id is already
 * installed: "folder" (a pack in the themes folder), "built-in" or null.
 */
export function validateArchive(file, { catalog, packsDir, builtInDir }) {
  const result = { id: null, name: null, errors: [], warnings: [], existing: null };
  let files = null;
  try {
    files = zipFiles(file);
    const loaded = loadPack(files);
    const { pack } = loaded;
    result.id = typeof pack.id === "string" ? pack.id : null;
    result.name = typeof pack.name === "string" ? pack.name : null;
    result.warnings.push(...applyAliases(pack, catalog.aliases));
    const checked = validatePack(loaded, catalog);
    result.errors.push(...checked.errors);
    result.warnings.push(...checked.warnings);
  } catch (e) {
    result.errors.push(files ? `theme.json could not be read: ${e.message}` : `the archive could not be read: ${e.message}`);
  } finally {
    files?.close();
  }
  if (result.id && PACK_ID.test(result.id)) {
    if (findPacks(packsDir).some((p) => p.id === result.id)) result.existing = "folder";
    else if (findPacks(builtInDir).some((p) => p.id === result.id)) result.existing = "built-in";
  }
  return result;
}

function checkId(id) {
  if (!PACK_ID.test(id) || RESERVED_IDS.has(id)) throw new Refusal(`"${id}" is not a pack that can be changed`);
}

function parkFolder(packsDir, id, path) {
  const parked = join(packsDir, CONVERTED_DIR);
  mkdirSync(parked, { recursive: true });
  const target = existsSync(join(parked, id)) ? join(parked, `${id}-${Date.now()}`) : join(parked, id);
  renameSync(path, target);
  return `${CONVERTED_DIR}/${basename(target)}/`;
}

/**
 * Packs in the themes folder are archives only: each folder pack is zipped to <id>.zip and the
 * folder moved to .converted/, keeping every file. A folder beside an archive of the same id is
 * moved aside too. Returns one note per pack, including any that couldn't be converted.
 */
export function convertFolderPacks(packsDir, pid) {
  const notes = [];
  for (const found of findPacks(packsDir)) {
    try {
      if (found.format === "zip" && found.shadowed) {
        notes.push(`the folder ${basename(found.shadowed)}/ was moved to ${parkFolder(packsDir, found.id, found.shadowed)} because ${found.id}${ZIP_EXT} is installed`);
      } else if (found.format === "folder") {
        const staged = join(packsDir, `.${found.id}.${pid}${ZIP_EXT}.tmp`);
        zipFolderPack(found.path, staged);
        renameSync(staged, join(packsDir, `${found.id}${ZIP_EXT}`));
        notes.push(`the folder pack "${found.id}" was converted to ${found.id}${ZIP_EXT}; its folder was moved to ${parkFolder(packsDir, found.id, found.path)}`);
      }
    } catch (e) {
      rmSync(join(packsDir, `.${found.id}.${pid}${ZIP_EXT}.tmp`), { force: true });
      notes.push(`the folder pack "${found.id}" couldn't be converted to ${ZIP_EXT} (${e.message}), so it isn't used`);
    }
  }
  return notes;
}

/**
 * Plans one operation. Returns { standIns, exclude, settings(s), verify(result), install(), cleanup() }:
 * stand-ins and excludes for the themes-folder source, the settings to save, a check of the compile
 * result, and the change to make once that build is live.
 */
export function planOperation(op, { packsDir, builtInDir, pid, catalog }) {
  const inFolder = (id) => findPacks(packsDir).find((p) => p.id === id);
  const isBuiltIn = (id) => findPacks(builtInDir).some((p) => p.id === id);
  const stagedPath = (id) => join(packsDir, `.${id}.${pid}${ZIP_EXT}.tmp`);
  let staged = null;
  const base = {
    standIns: [],
    exclude: [],
    settings: (s) => s,
    verify: () => {},
    install: () => null,
    cleanup: () => {
      if (staged) rmSync(staged, { force: true });
    },
  };
  // The staged archive must compile before anything is installed.
  const mustCompile = (id, action) => (result) => {
    const pack = result.packs.find((p) => p.id === id);
    if (!pack?.valid) throw new Refusal(`"${id}" can't be ${action}: ${pack?.errors.join("; ") || "it did not compile"}`);
  };

  switch (op.kind) {
    case "select": {
      const theme = op.theme;
      if (theme !== STOCK_ID && theme !== RANDOM_ID && (!PACK_ID.test(theme) || RESERVED_IDS.has(theme))) {
        throw new Refusal(`"${theme}" is not a valid theme id`);
      }
      if (op.random !== undefined) {
        const keys = Object.keys(RANDOM_POOL_DEFAULTS);
        if (!op.random || typeof op.random !== "object" || Object.entries(op.random).some(([k, v]) => !keys.includes(k) || typeof v !== "boolean")) {
          throw new Refusal(`Random's groups must be true or false for ${keys.join(", ")}`);
        }
      }
      return { ...base, settings: (s) => ({ ...s, theme, random: { ...s.random, ...(op.random ?? {}) } }) };
    }

    case "install": {
      const checked = validateArchive(op.file, { catalog, packsDir, builtInDir });
      if (checked.errors.length) throw new Refusal(`the pack can't be installed: ${checked.errors.join("; ")}`);
      const id = checked.id;
      checkId(id);
      const found = inFolder(id);
      if (found && !op.replace) throw new Refusal(`"${id}" is already installed; confirm to replace it`);
      if (!found && checked.existing === "built-in") {
        throw new Refusal(`"${id}" is a built-in pack and can't be replaced by an upload; give the pack a new id`);
      }
      staged = stagedPath(id);
      copyFileSync(op.file, staged);
      return {
        ...base,
        standIns: [{ id, format: "zip", path: staged }],
        verify: mustCompile(id, "installed"),
        install: () => {
          renameSync(staged, join(packsDir, `${id}${ZIP_EXT}`));
          staged = null;
          return found ? `"${checked.name}" replaced the pack "${id}"` : `"${checked.name}" was added as "${id}"`;
        },
      };
    }

    case "rename": {
      checkId(op.id);
      const problem = badPackName(op.name);
      if (problem) throw new Refusal(problem);
      const name = op.name.trim();
      const found = inFolder(op.id);
      // A built-in pack's archive ships in the image, so its new name is kept in themeable.json.
      if (!found) {
        if (!isBuiltIn(op.id)) throw new Refusal(`there is no pack "${op.id}"`);
        return {
          ...base,
          settings: (s) => ({ ...s, names: { ...s.names, [op.id]: name } }),
          install: () => `"${op.id}" is now named "${name}"`,
        };
      }
      staged = stagedPath(op.id);
      rewriteZipPack(found.path, staged, (pack) => ({ ...pack, name }));
      return {
        ...base,
        standIns: [{ id: op.id, format: "zip", path: staged }],
        verify: mustCompile(op.id, "renamed"),
        install: () => {
          renameSync(staged, found.path);
          staged = null;
          return `"${op.id}" is now named "${name}"`;
        },
      };
    }

    case "reset-name": {
      checkId(op.id);
      if (inFolder(op.id) || !isBuiltIn(op.id)) throw new Refusal(`only a renamed built-in pack has a name to reset`);
      return {
        ...base,
        settings: (s) => {
          const { [op.id]: _, ...names } = s.names;
          return { ...s, names };
        },
        install: () => `"${op.id}" has its original name again`,
      };
    }

    case "delete": {
      checkId(op.id);
      const found = inFolder(op.id);
      const fallBack = (s) => (s.theme === op.id ? { ...s, theme: STOCK_ID } : s);
      if (found) {
        return {
          ...base,
          exclude: [op.id],
          settings: fallBack,
          install: () => {
            unlinkSync(found.path);
            return `"${op.id}" was deleted`;
          },
        };
      }
      if (!isBuiltIn(op.id)) throw new Refusal(`there is no pack "${op.id}"`);
      return {
        ...base,
        settings: (s) => fallBack({ ...s, hidden: [...new Set([...s.hidden, op.id])].sort() }),
        install: () => `the built-in pack "${op.id}" is hidden; restore built-in packs to bring it back`,
      };
    }

    case "restore":
      return { ...base, settings: (s) => ({ ...s, hidden: [] }), install: () => "the built-in packs are all shown again" };

    default:
      return base;
  }
}
