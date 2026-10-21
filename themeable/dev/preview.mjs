#!/usr/bin/env node
// Serves a frontend build like the romm-themeable image does, through the real patched nginx.
// Options and the stub API: "Previewing without Docker" in themeable/README.md.
import { spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { fail, parseArgs } from "../lib/args.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const mod = resolve(here, "..");
const repo = resolve(mod, "..");
const args = parseArgs();
const port = Number(args.port ?? 8099);
const apiPort = Number(args["api-port"] ?? port + 1);
const work = resolve(args.work ?? join(tmpdir(), "themeable-preview"));
const dist = resolve(args.dist ?? join(repo, "frontend/dist"));
if (!existsSync(join(dist, "index.html"))) fail(`no frontend build at ${dist}; run \`npm run build\` in frontend/ or pass --dist`);

const run = (script, extraEnv = {}, ...a) => {
  const r = spawnSync(process.execPath, [join(moduleDir, script), ...a], { stdio: "inherit", env: { ...process.env, ...extraEnv } });
  if (r.status !== 0) fail(`${script} failed`);
};

rmSync(work, { recursive: true, force: true });
const web = join(work, "html");
const moduleDir = join(work, "module");
const runtimeDir = join(work, "runtime");
const packsFolder = resolve(args["packs-folder"] ?? join(work, "themes"));
mkdirSync(packsFolder, { recursive: true });

// 1. A web root shaped like the image: frontend build plus frontend/assets.
cpSync(dist, web, { recursive: true });
cpSync(join(repo, "frontend/assets"), join(web, "assets"), { recursive: true, filter: (src) => !src.includes("/assets/romm") });

// 2. The module as the image holds it, with a catalog taken from this build.
cpSync(mod, moduleDir, { recursive: true, filter: (src) => !/\/(dist|node_modules)(\/|$)/.test(src.slice(mod.length)) });
// Built-in packs ship as archives in the image, so the preview zips them the same way.
run("scripts/zip-packs.mjs", {}, "--packs", join(mod, "packs"), "--out", join(moduleDir, "packs"));
run("scripts/catalog.mjs", {}, "--tokens", join(dist, "assets"), "--assets-dir", join(web, "assets"), "--no-src",
  "--css-refs-from", join(mod, "catalog/assets.json"), "--out", join(moduleDir, "catalog"));
run("scripts/apply-hooks.mjs", {}, "--webroot", dist, "--nginx", join(repo, "docker/nginx/templates/default.conf.template"), "--out", join(work, "hooks"));
for (const f of ["index.html", "sw.js"]) {
  cpSync(join(work, "hooks", f), join(web, f));
  rmSync(join(web, `${f}.gz`), { force: true });
}
symlinkSync(join(runtimeDir, "current/themes"), join(web, "themes"));
symlinkSync(join(runtimeDir, "current/themeable"), join(web, "themeable"));

// 3. What the container's entrypoint does: compile the built-in and folder packs.
const runtimeEnv = { THEMEABLE_HOME: moduleDir, THEMEABLE_PACKS_PATH: packsFolder, THEMEABLE_RUNTIME_DIR: runtimeDir };
run("scripts/runtime.mjs", runtimeEnv, ...(args.default ? ["--select", String(args.default)] : []));

// 4. Render the template like the image's envsubst step, minus the njs-only location.
const env = { DEV_PORT: String(apiPort), ROMM_PORT: String(port), IPV6_LISTEN: "", NGINX_ACCESS_LOG: "access_log off;", ROMM_BASE_PATH: work, ROMM_CACHE_BASE_PATH: join(work, "cache") };
const conf = readFileSync(join(work, "hooks/default.conf.template"), "utf8")
  .replace(/\$\{([A-Z0-9_]+)\}/g, (m, k) => env[k] ?? m)
  .replace("root /var/www/html;", `root ${web};`)
  .replace(/\n\s*# Internal decoding endpoint[^\n]*\n\s*location \/decode \{[^}]*\}/, "");
const nginxDir = join(work, "nginx");
mkdirSync(join(nginxDir, "tmp"), { recursive: true });
writeFileSync(join(nginxDir, "site.conf"), conf);
const mime = ["/etc/nginx/mime.types", "/usr/local/etc/nginx/mime.types", "/opt/homebrew/etc/nginx/mime.types"].find(existsSync);
writeFileSync(
  join(nginxDir, "nginx.conf"),
  `daemon off;\n${process.getuid?.() === 0 ? "user root;\n" : ""}worker_processes 1;\npid ${nginxDir}/nginx.pid;\nerror_log stderr;\nevents {}\nhttp {\n` +
    `  client_body_temp_path ${nginxDir}/tmp/body; proxy_temp_path ${nginxDir}/tmp/proxy;\n` +
    `  fastcgi_temp_path ${nginxDir}/tmp/fcgi; uwsgi_temp_path ${nginxDir}/tmp/uwsgi; scgi_temp_path ${nginxDir}/tmp/scgi;\n` +
    (mime ? `  include ${mime};\n` : "") +
    `  default_type application/octet-stream;\n  include ${nginxDir}/site.conf;\n}\n`,
);
const test = spawnSync("nginx", ["-e", "stderr", "-t", "-p", nginxDir, "-c", join(nginxDir, "nginx.conf")], { encoding: "utf8" });
if (test.status !== 0) fail(`nginx rejected the patched config:\n${test.stderr}`);

// 5. Without a backend, a stub API: heartbeat succeeds, everything else answers 401.
const api = args["api-port"]
  ? null
  : createServer((req, res) => {
      const ok = req.url.startsWith("/api/heartbeat");
      res.writeHead(ok ? 200 : 401, { "content-type": "application/json" });
      res.end(ok ? "{}" : JSON.stringify({ detail: "Not authenticated (preview stub)" }));
    }).listen(apiPort, "127.0.0.1");

const nginx = spawn("nginx", ["-e", "stderr", "-p", nginxDir, "-c", join(nginxDir, "nginx.conf")], { stdio: "inherit" });
const stop = () => {
  nginx.kill();
  api?.close();
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
nginx.on("exit", (code) => {
  api?.close();
  process.exitCode = code ?? 0;
});
console.log(`themeable: preview at http://localhost:${port}/ (themes: http://localhost:${port}/themeable/)`);
console.log(
  `themeable: backend environment: ${Object.entries(runtimeEnv)
    .map(([k, v]) => `${k}=${v}`)
    .join(" ")}`,
);
