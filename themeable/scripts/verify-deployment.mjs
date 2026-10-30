#!/usr/bin/env node
// Deploys an image with the root docker-compose.yml, as an admin would, and checks it runs:
// health, versions, the theme hooks, the sandbox headers and a start-up log free of errors.
import { execFileSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";
import { COOKIE, PREVIEW_SLOTS } from "../lib/client.mjs";
import { SANDBOX_POLICY } from "../lib/nginx.mjs";

const home = join(dirname(fileURLToPath(import.meta.url)), "..");
const repo = join(home, "..");
const args = parseArgs();
const romm = readFileSync(join(home, "ROMM_VERSION"), "utf8").trim();
const version = String(args["expect-version"] ?? JSON.parse(readFileSync(join(home, "package.json"), "utf8")).version);
const image = String(args.image ?? `ghcr.io/stealthx3/romm-themeable:${romm}`);
const port = Number(args.port ?? 18080);
const project = "themeable-verify";
const base = `http://127.0.0.1:${port}`;
// Log lines that mean something went wrong, whatever logged them.
const LOG_ERRORS = /Traceback|\bERROR\b|\bCRITICAL\b|themeable: .*(failed|could not|couldn't|can't be)/;

const work = mkdtempSync(join(tmpdir(), "themeable-verify-"));
// The container's user differs from the caller's, so its folders are open to everyone.
for (const dir of ["library", "assets", "config", "themes"]) {
  mkdirSync(join(work, dir));
  chmodSync(join(work, dir), 0o777);
}
const override = join(work, "override.yml");
// Fresh secrets and folders replace the compose file's placeholders; nothing else changes.
writeFileSync(
  override,
  `services:
  romm:
    image: ${image}
    container_name: ${project}-romm
    environment:
      - DB_PASSWD=verify-db
      - ROMM_AUTH_SECRET_KEY=${execFileSync("openssl", ["rand", "-hex", "32"], { encoding: "utf8" }).trim()}
    volumes:
      - ${work}/library:/romm/library
      - ${work}/assets:/romm/assets
      - ${work}/config:/romm/config
      - ${work}/themes:/romm/themes
    ports: !override
      - "127.0.0.1:${port}:8080"
  romm-db:
    container_name: ${project}-db
    environment:
      - MARIADB_ROOT_PASSWORD=verify-root
      - MARIADB_PASSWORD=verify-db
`,
);

const compose = (...rest) =>
  execFileSync("docker", ["compose", "-p", project, "-f", join(repo, "docker-compose.yml"), "-f", override, ...rest], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    maxBuffer: 64 * 1024 * 1024,
  });

const problems = [];
const check = (ok, message) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${message}`);
  if (!ok) problems.push(message);
};
const get = async (path) => {
  const res = await fetch(base + path);
  return { status: res.status, headers: res.headers, body: Buffer.from(await res.arrayBuffer()) };
};

try {
  console.log(`themeable: deploying ${image} with docker-compose.yml`);
  compose("up", "-d", "--wait", "--wait-timeout", "300");

  const heartbeat = await get("/api/heartbeat");
  const system = heartbeat.status === 200 ? JSON.parse(heartbeat.body).SYSTEM : null;
  check(system?.VERSION === romm, `RomM reports version ${system?.VERSION} (expected ${romm})`);
  const inside = (file) => compose("exec", "-T", "romm", "cat", file);
  check(JSON.parse(inside("/themeable/package.json")).version === version, `the image carries module version ${version}`);
  check(inside("/themeable/ROMM_VERSION").trim() === romm, `the image was built for RomM ${romm}`);

  const status = JSON.parse(inside("/tmp/themeable/status.json"));
  check(status.ok === true, `the start-up compile succeeded${status.error ? `: ${status.error}` : ""}`);
  const broken = (status.packs ?? []).filter((p) => !p.valid).map((p) => p.id);
  check(status.packs?.length > 0 && !broken.length, `every built-in pack compiled${broken.length ? ` (not: ${broken.join(", ")})` : ""}`);

  const index = await get("/");
  check(index.status === 200 && index.body.toString().includes("/themeable/loader.js"), "index.html loads the theme loader");
  check((await get("/themeable/loader.js")).status === 200, "the loader is served");
  const pack = status.packs?.find((p) => p.valid)?.id;
  const css = await get(`/themes/${pack}/theme.css`);
  check(css.status === 200, `the ${pack} stylesheet is served`);
  check(css.headers.get("content-security-policy") === SANDBOX_POLICY && css.headers.get("x-content-type-options") === "nosniff", "/themes/ is sandboxed");
  const stock = await get(PREVIEW_SLOTS.logo);
  const themed = await get(`${PREVIEW_SLOTS.logo}?${COOKIE}=${pack}`);
  check(themed.status === 200 && !themed.body.equals(stock.body), `nginx serves ${pack}'s artwork for its cookie value`);
  check((await get(`/themes/${pack}/missing.html`)).status === 404, "a missing file under /themes/ is a 404");

  const logs = compose("logs", "--no-color", "romm");
  const errors = logs.split("\n").filter((line) => LOG_ERRORS.test(line));
  check(!errors.length, `the start-up log has no errors${errors.length ? `:\n${errors.slice(0, 20).join("\n")}` : ""}`);
} catch (e) {
  problems.push(e.stderr?.toString() || e.message);
  console.error(e.stderr?.toString() || e.message);
} finally {
  if (problems.length) {
    try {
      console.log(compose("logs", "--no-color", "--tail", "200"));
    } catch {}
  }
  if (!args.keep) {
    try {
      compose("down", "-v", "--remove-orphans");
    } catch {}
    try {
      rmSync(work, { recursive: true, force: true });
    } catch {}
  }
}
if (problems.length) fail(`${problems.length} deployment check(s) failed for ${image}`);
console.log(`themeable: ${image} deploys and runs as expected`);
