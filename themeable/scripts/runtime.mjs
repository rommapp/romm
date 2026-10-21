#!/usr/bin/env node
// Compiles the built-in and folder packs in the running container (at start-up and on save);
// builds go to <runtime>/builds/<n> and `current` swaps to one in a single rename.
import { createHash } from "node:crypto";
import {
  accessSync,
  closeSync,
  constants,
  existsSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  realpathSync,
  renameSync,
  rmSync,
  statSync,
  symlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "../lib/args.mjs";
import { loadCatalog } from "../lib/catalog.mjs";
import { CLIENT, RANDOM_ID } from "../lib/client.mjs";
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
// Saved in each build, so the next compile can reuse its unchanged archives.
const CACHE_FILE = "packs-cache.json";

/** Changes whenever the compiler or catalog does, so a build from older code is never reused. */
function compilerKey() {
  const hash = createHash("sha256");
  for (const dir of ["lib", "catalog"]) {
    for (const name of readdirSync(join(home, dir)).sort()) hash.update(name).update(readFileSync(join(home, dir, name)));
  }
  return hash.digest("hex").slice(0, 16);
}

function previousBuild(link) {
  try {
    const dir = realpathSync(link);
    return { key: compilerKey(), dir, packs: JSON.parse(readFileSync(join(dir, CACHE_FILE), "utf8")) };
  } catch {
    return { key: compilerKey(), dir: null, packs: {} };
  }
}

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

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}

// The lock holds its owner's pid, so a run that was killed doesn't block the next one.
function lockIsStale() {
  try {
    const pid = Number(readFileSync(lockFile, "utf8").trim());
    if (Number.isInteger(pid) && pid > 0 && !alive(pid)) return true;
    return Date.now() - statSync(lockFile).mtimeMs > 120000;
  } catch {
    return true;
  }
}

function acquireLock() {
  const deadline = Date.now() + 30000;
  for (;;) {
    try {
      const fd = openSync(lockFile, "wx");
      writeSync(fd, String(process.pid));
      closeSync(fd);
      return;
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      if (lockIsStale()) rmSync(lockFile, { force: true });
      else if (Date.now() > deadline) throw new Error("another theme compile is still running");
      else Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 250);
    }
  }
}

function run() {
  mkdirSync(join(runtimeDir, "builds"), { recursive: true });
  const notes = [];

  // A new selection is staged now (so an unwritable folder fails before any work) and
  // only replaces themeable.json once its build is live, so a killed save changes nothing.
  let selection;
  let stagedSettings = null;
  if (args.select !== undefined) {
    const theme = String(args.select);
    if (theme !== STOCK_ID && theme !== RANDOM_ID && (!PACK_ID.test(theme) || RESERVED_IDS.has(theme))) throw new Error(`"${theme}" is not a valid theme id`);
    if (!existsSync(packsDir)) mkdirSync(packsDir, { recursive: true });
    stagedSettings = `${settingsFile}.${process.pid}.tmp`;
    writeFileSync(stagedSettings, JSON.stringify({ theme, updated: new Date().toISOString() }, null, 2) + "\n");
    selection = { theme, note: null };
  } else {
    selection = readSelection(settingsFile);
  }
  if (selection.note) notes.push(selection.note);

  const catalog = loadCatalog(join(home, "catalog"));
  const entries = collectPacks([
    { dir: join(home, "packs"), source: "built-in" },
    { dir: packsDir, source: "folder" },
  ]);

  const id = `${Date.now()}-${process.pid}`;
  const buildDir = join(runtimeDir, "builds", id);
  const link = join(runtimeDir, "current");
  const result = compileAll({
    entries,
    catalog,
    outDir: buildDir,
    selected: selection.theme,
    loaderSource: readFileSync(join(home, "loader", "loader.js"), "utf8"),
    pickerFile: join(home, "picker", "index.html"),
    reuse: previousBuild(link),
  });
  if (result.reason) notes.push(result.reason);
  writeFileSync(join(buildDir, CACHE_FILE), JSON.stringify(result.cache));

  const tmpLink = `${link}.${process.pid}`;
  rmSync(tmpLink, { force: true });
  symlinkSync(join("builds", id), tmpLink);
  renameSync(tmpLink, link);
  if (stagedSettings) renameSync(stagedSettings, settingsFile);
  for (const old of readdirSync(join(runtimeDir, "builds"))) {
    if (old !== id) rmSync(join(runtimeDir, "builds", old), { recursive: true, force: true });
  }

  const status = {
    ok: true,
    generated: new Date().toISOString(),
    selected: result.selected,
    effective: result.effective,
    client: CLIENT,
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
    rmSync(`${settingsFile}.${process.pid}.tmp`, { force: true });
    rmSync(lockFile, { force: true });
  }
} catch (e) {
  // The previous build (if any) keeps serving; with none, the loader 404s and RomM shows its own look.
  status = { ok: false, generated: new Date().toISOString(), error: e.message, client: CLIENT, folder: folderInfo() };
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
