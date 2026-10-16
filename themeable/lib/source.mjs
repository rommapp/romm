// Applies the module's additions to a copy of RomM's source: new files from
// overlay/ (which must not already exist upstream) and the anchored patches in
// patches/, in file-name order. Upstream files in the repository stay untouched.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { pathToFileURL } from "node:url";

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

/** Copies overlay files into root. `only` limits it to a top-level folder such as "frontend". */
export function applyOverlay(overlayDir, root, { only, skipTests = false } = {}) {
  const copied = [];
  if (!existsSync(overlayDir)) return copied;
  for (const file of walk(overlayDir)) {
    const rel = relative(overlayDir, file).split(sep).join("/");
    if (only && !rel.startsWith(`${only}/`)) continue;
    if (skipTests && /(^|\/)tests\//.test(rel)) continue;
    const target = join(root, rel);
    if (existsSync(target) && !readFileSync(target).equals(readFileSync(file))) {
      throw new Error(`overlay file ${rel} would replace an upstream file; rename it or turn it into a patch`);
    }
    mkdirSync(dirname(target), { recursive: true });
    copyFileSync(file, target);
    copied.push(rel);
  }
  return copied;
}

/** Overlay file paths relative to the repository root. */
export function overlayFiles(overlayDir) {
  if (!existsSync(overlayDir)) return [];
  return walk(overlayDir).map((f) => relative(overlayDir, f).split(sep).join("/"));
}

export async function loadPatches(patchesDir) {
  if (!existsSync(patchesDir)) return [];
  const names = readdirSync(patchesDir).filter((f) => f.endsWith(".mjs")).sort();
  const patches = [];
  for (const name of names) {
    const mod = await import(pathToFileURL(join(patchesDir, name)).href);
    patches.push({ name, file: mod.file, description: mod.description, apply: mod.apply });
  }
  return patches;
}

/** Applies every patch whose file is under root (and `only`, if given). Throws on the first failure. */
export async function applyPatches(patchesDir, root, { only } = {}) {
  const applied = [];
  for (const patch of await loadPatches(patchesDir)) {
    if (only && !patch.file.startsWith(`${only}/`)) continue;
    const target = join(root, patch.file);
    if (!existsSync(target)) throw new Error(`patch ${patch.name}: ${patch.file} does not exist upstream any more`);
    let result;
    try {
      result = patch.apply(readFileSync(target, "utf8"));
    } catch (e) {
      throw new Error(`patch ${patch.name} (${patch.description}) no longer applies to ${patch.file}: ${e.message}`);
    }
    writeFileSync(target, result);
    applied.push(patch.name);
  }
  return applied;
}
