#!/usr/bin/env node
// Compiles the built-in packs plus the packs in the mapped themes folder, inside the
// running container. Runs at start-up (docker/entrypoint.sh) and when an admin saves
// the Branding tab (via the backend). Prints the resulting status as JSON.
//
//   node scripts/runtime.mjs [--select <pack id>|none]
//
// Environment: THEMEABLE_PACKS_PATH (default /romm/themes), THEMEABLE_RUNTIME_DIR
// (default /tmp/themeable). Output goes to <runtime>/builds/<n>, and <runtime>/current
// is swapped to it in one rename, so nginx never serves a half-written build.
import {
  accessSync,
  closeSync,
  constants,
  existsSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  renameSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "../lib/args.mjs";
import { loadCatalog } from "../lib/catalog.mjs";
import { collectPacks, compileAll, readSelection, STOCK_ID } from "../lib/compile.mjs";
import { PACK_ID, RESERVED_IDS } from "../lib/pack.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const home = resolve(here, "..");
const args = parseArgs();
const packsDir = resolve(process.env.THEMEABLE_PACKS_PATH || "/romm/themes");
const runtimeDir = resolve(process.env.THEMEABLE_RUNTIME_DIR || "/tmp/themeable");
const settingsFile = join(packsDir, "themeable.json");
const statusFile = join(runtimeDir, "status.json");
const lockFile = join(runtimeDir, "compile.lock");

function folderInfo() {
  const exists = existsSync(packsDir) && statSync(packsDir).isDirectory();
  let writable = false;
  try {
    accessSync(packsDir, constants.W_OK);
    writable = exists;
  } catch {
    writable = false;
  }
  let mounted = false;
  try {
    mounted = readFileSync("/proc/self/mountinfo", "utf8")
      .split("\n")
      .some((line) => line.split(" ")[4] === packsDir);
  } catch {
    mounted = false;
  }
  return { path: packsDir, exists, writable, mounted };
}

function writeJsonAtomic(file, data) {
  const tmp = `${file}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n");
  renameSync(tmp, file);
}

function acquireLock() {
  const deadline = Date.now() + 30000;
  for (;;) {
    try {
      closeSync(openSync(lockFile, "wx"));
      return;
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      // A lock older than two minutes belongs to a run that died.
      if (Date.now() - statSync(lockFile).mtimeMs > 120000) rmSync(lockFile, { force: true });
      else if (Date.now() > deadline) throw new Error("another theme compile is still running");
      else Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 250);
    }
  }
}

function run() {
  mkdirSync(join(runtimeDir, "builds"), { recursive: true });
  const notes = [];

  if (args.select !== undefined) {
    const theme = String(args.select);
    if (theme !== STOCK_ID && (!PACK_ID.test(theme) || RESERVED_IDS.has(theme))) throw new Error(`"${theme}" is not a valid theme id`);
    if (!existsSync(packsDir)) mkdirSync(packsDir, { recursive: true });
    writeJsonAtomic(settingsFile, { theme, updated: new Date().toISOString() });
  }

  const selection = readSelection(settingsFile);
  if (selection.note) notes.push(selection.note);

  const catalog = loadCatalog(join(home, "catalog"));
  const entries = collectPacks([
    { dir: join(home, "packs"), source: "built-in" },
    { dir: packsDir, source: "folder" },
  ]);

  const id = `${Date.now()}-${process.pid}`;
  const buildDir = join(runtimeDir, "builds", id);
  const result = compileAll({
    entries,
    catalog,
    outDir: buildDir,
    selected: selection.theme,
    loaderSource: readFileSync(join(home, "loader", "loader.js"), "utf8"),
    pickerFile: join(home, "picker", "index.html"),
  });
  if (result.reason) notes.push(result.reason);

  const link = join(runtimeDir, "current");
  const tmpLink = `${link}.${process.pid}`;
  rmSync(tmpLink, { force: true });
  symlinkSync(join("builds", id), tmpLink);
  renameSync(tmpLink, link);
  for (const old of readdirSync(join(runtimeDir, "builds"))) {
    if (old !== id) rmSync(join(runtimeDir, "builds", old), { recursive: true, force: true });
  }

  const status = {
    ok: true,
    generated: new Date().toISOString(),
    selected: result.selected,
    effective: result.effective,
    notes,
    folder: folderInfo(),
    packs: result.packs,
  };
  writeJsonAtomic(statusFile, status);
  return status;
}

let status;
try {
  mkdirSync(runtimeDir, { recursive: true });
  acquireLock();
  try {
    status = run();
  } finally {
    rmSync(lockFile, { force: true });
  }
} catch (e) {
  // The previous build (if any) keeps serving; with none, the loader 404s and RomM shows its own look.
  status = { ok: false, generated: new Date().toISOString(), error: e.message, folder: folderInfo() };
  try {
    writeJsonAtomic(statusFile, { ...(existsSync(statusFile) ? JSON.parse(readFileSync(statusFile, "utf8")) : {}), ...status });
  } catch {
    // Nothing more to record; the exit code and stdout carry the error.
  }
}
for (const p of status.packs ?? []) {
  for (const e of p.errors) console.error(`themeable: ${p.source} pack "${p.id}": ${e}`);
}
for (const n of status.notes ?? []) console.error(`themeable: ${n}`);
if (status.error) console.error(`themeable: ${status.error}`);
process.stdout.write(JSON.stringify(status) + "\n");
process.exit(status.ok ? 0 : 1);
