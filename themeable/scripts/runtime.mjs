#!/usr/bin/env node
// Compiles every pack at container start-up and for each Branding change (lib/manage.mjs); builds go
// to <runtime>/builds/<n> and `current` switches to one in a single rename.
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
import { CLIENT } from "../lib/client.mjs";
import { collectPacks, compileAll, readSelection } from "../lib/compile.mjs";
import { convertFolderPacks, planOperation, Refusal, validateArchive } from "../lib/manage.mjs";
import { findPacks } from "../lib/packfiles.mjs";

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

/** The one change this run makes, from the command line; with none it just recompiles. */
function requestedOperation() {
  if (args.select !== undefined) {
    let random;
    if (args["random-pool"] !== undefined) {
      try {
        random = JSON.parse(String(args["random-pool"]));
      } catch {
        throw new Refusal("--random-pool must be JSON");
      }
    }
    return { kind: "select", theme: String(args.select), random };
  }
  if (args.install !== undefined) return { kind: "install", file: resolve(String(args.install)), replace: args.replace === true };
  if (args.rename !== undefined) {
    // Read verbatim, so a name starting with "--" isn't taken for an option.
    const at = process.argv.indexOf("--name");
    return { kind: "rename", id: String(args.rename), name: at > 0 ? (process.argv[at + 1] ?? "") : "" };
  }
  if (args["reset-name"] !== undefined) return { kind: "reset-name", id: String(args["reset-name"]) };
  if (args.delete !== undefined) return { kind: "delete", id: String(args.delete) };
  if (args["restore-built-ins"]) return { kind: "restore" };
  return { kind: "recompile" };
}

function run() {
  mkdirSync(join(runtimeDir, "builds"), { recursive: true });
  const notes = [];

  const catalog = loadCatalog(join(home, "catalog"));
  const builtInDir = join(home, "packs");
  const saved = readSelection(settingsFile);
  if (saved.note) notes.push(saved.note);
  // The themes folder holds archives only; folder packs left from older versions are converted first.
  if (existsSync(packsDir)) notes.push(...convertFolderPacks(packsDir, process.pid));
  const operation = planOperation(requestedOperation(), { packsDir, builtInDir, pid: process.pid, catalog });
  cleanups.push(operation.cleanup);
  const settings = operation.settings({ theme: saved.theme, hidden: saved.hidden, random: saved.random, names: saved.names });

  // Changed settings are staged now, so an unwritable folder fails before any work.
  let stagedSettings = null;
  const changed =
    settings.theme !== saved.theme ||
    settings.hidden.join() !== saved.hidden.join() ||
    JSON.stringify(settings.random) !== JSON.stringify(saved.random) ||
    JSON.stringify(settings.names) !== JSON.stringify(saved.names);
  if (changed || args.select !== undefined) {
    if (!existsSync(packsDir)) mkdirSync(packsDir, { recursive: true });
    stagedSettings = `${settingsFile}.${process.pid}.tmp`;
    writeFileSync(stagedSettings, JSON.stringify({ ...settings, updated: new Date().toISOString() }, null, 2) + "\n");
    cleanups.push(() => rmSync(stagedSettings, { force: true }));
  }

  const entries = collectPacks([
    { dir: builtInDir, source: "built-in", exclude: settings.hidden },
    { dir: packsDir, source: "folder", exclude: operation.exclude, standIns: operation.standIns, archivesOnly: true },
  ]);

  const id = `${Date.now()}-${process.pid}`;
  const buildDir = join(runtimeDir, "builds", id);
  const link = join(runtimeDir, "current");
  const result = compileAll({
    entries,
    catalog,
    outDir: buildDir,
    selected: settings.theme,
    randomPool: settings.random,
    names: settings.names,
    loaderSource: readFileSync(join(home, "loader", "loader.js"), "utf8"),
    pickerFile: join(home, "picker", "index.html"),
    reuse: previousBuild(link),
  });
  if (result.reason) notes.push(result.reason);
  try {
    operation.verify(result);
  } catch (e) {
    rmSync(buildDir, { recursive: true, force: true });
    throw e;
  }
  writeFileSync(join(buildDir, CACHE_FILE), JSON.stringify(result.cache));

  // Settings and the pack change land before the new build goes live; if either fails, both are
  // undone and the previous build keeps serving.
  const previousSettings = stagedSettings && existsSync(settingsFile) ? readFileSync(settingsFile) : null;
  try {
    if (stagedSettings) renameSync(stagedSettings, settingsFile);
    const done = operation.install();
    if (done) notes.push(done);
  } catch (e) {
    if (stagedSettings && !existsSync(stagedSettings)) {
      if (previousSettings) writeFileSync(settingsFile, previousSettings);
      else rmSync(settingsFile, { force: true });
    }
    rmSync(buildDir, { recursive: true, force: true });
    throw e;
  }

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
    client: CLIENT,
    notes,
    hidden: settings.hidden.filter((id) => findPacks(builtInDir).some((p) => p.id === id)),
    random: result.random,
    folder: folderInfo(),
    packs: result.packs,
  };
  writeJsonAtomic(statusFile, status);
  return status;
}

// --validate-archive only reads: it reports on an uploaded archive and exits, without the lock.
if (args["validate-archive"] !== undefined) {
  const report = validateArchive(resolve(String(args["validate-archive"])), {
    catalog: loadCatalog(join(home, "catalog")),
    packsDir,
    builtInDir: join(home, "packs"),
  });
  process.stdout.write(JSON.stringify({ ok: report.errors.length === 0, ...report }) + "\n");
  process.exit(report.errors.length ? 1 : 0);
}

const cleanups = [];
let status;
try {
  mkdirSync(runtimeDir, { recursive: true });
  acquireLock();
  try {
    status = run();
  } finally {
    rmSync(`${settingsFile}.${process.pid}.tmp`, { force: true });
    for (const cleanup of cleanups) cleanup();
    rmSync(lockFile, { force: true });
  }
} catch (e) {
  // The previous build (if any) keeps serving; with none, the loader 404s and RomM shows its own look.
  let previous = {};
  try {
    previous = existsSync(statusFile) ? JSON.parse(readFileSync(statusFile, "utf8")) : {};
  } catch {
    previous = {};
  }
  const failure = { ok: false, generated: new Date().toISOString(), error: e.message, client: CLIENT, folder: folderInfo() };
  status = { ...previous, ...failure };
  if (!(e instanceof Refusal)) {
    try {
      writeJsonAtomic(statusFile, status);
    } catch {
      // Nothing more to record; the exit code and stdout carry the error.
    }
  }
}
for (const p of status.packs ?? []) {
  for (const e of p.errors) console.error(`themeable: ${p.source} pack "${p.id}": ${e}`);
}
for (const n of status.notes ?? []) console.error(`themeable: ${n}`);
if (status.error) console.error(`themeable: ${status.error}`);
process.stdout.write(JSON.stringify(status) + "\n");
process.exit(status.ok ? 0 : 1);
