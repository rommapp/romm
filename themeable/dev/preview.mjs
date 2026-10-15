#!/usr/bin/env node
// Local preview without Docker: lays out a web root like the RomM image from a
// frontend build, applies the module exactly as the Dockerfile does, and serves it
// with the real (patched) nginx template. The API is a stub that answers
// "logged out", which is enough to see the login screen and the theme picker.
//
//   cd frontend && npm run build
//   node themeable/dev/preview.mjs [--default ember] [--port 8099]
//
// Needs nginx on PATH. Ctrl-C stops both servers.
import { spawn, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
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
const apiPort = port + 1;
const defaultTheme = args.default ?? "ember";
const work = resolve(args.work ?? join(tmpdir(), "themeable-preview"));
const dist = join(repo, "frontend/dist");
if (!existsSync(join(dist, "index.html"))) fail("no frontend/dist; run `npm run build` in frontend/ first");

const run = (script, ...a) => {
  const r = spawnSync(process.execPath, [join(mod, script), ...a], { stdio: "inherit" });
  if (r.status !== 0) fail(`${script} failed`);
};

// 1. A web root shaped like the image: build output plus frontend/assets.
rmSync(work, { recursive: true, force: true });
const web = join(work, "html");
cpSync(dist, web, { recursive: true });
cpSync(join(repo, "frontend/assets"), join(web, "assets"), { recursive: true, dereference: false, filter: (src) => !src.includes("/assets/romm") });

// 2. The Dockerfile's build stage.
const out = join(work, "out");
mkdirSync(join(out, "catalog"), { recursive: true });
cpSync(join(mod, "catalog/token-aliases.json"), join(out, "catalog/token-aliases.json"));
run("scripts/catalog.mjs", "--tokens", join(web, "assets"), "--assets-dir", join(web, "assets"), "--no-src", "--out", join(out, "catalog"));
run("scripts/build.mjs", "--catalog", join(out, "catalog"), "--out", join(out, "web"), "--default", defaultTheme);
mkdirSync(join(out, "web/root"), { recursive: true });
run(
  "scripts/apply-hooks.mjs",
  "--webroot", web,
  "--nginx", join(repo, "docker/nginx/templates/default.conf.template"),
  "--root-overlay", join(out, "web/root"),
  "--out", join(out, "hooks"),
  "--default", defaultTheme,
);

// 3. The Dockerfile's final stage.
cpSync(join(out, "web/themes"), join(web, "themes"), { recursive: true });
cpSync(join(out, "web/themeable"), join(web, "themeable"), { recursive: true });
cpSync(join(out, "web/root"), web, { recursive: true });
for (const f of ["index.html", "sw.js"]) {
  cpSync(join(out, "hooks", f), join(web, f));
  rmSync(join(web, `${f}.gz`), { force: true });
}

// 4. Render the template like the image's envsubst step, minus the njs-only location.
const env = { DEV_PORT: String(apiPort), ROMM_PORT: String(port), IPV6_LISTEN: "", NGINX_ACCESS_LOG: "access_log off;", ROMM_BASE_PATH: work, ROMM_CACHE_BASE_PATH: join(work, "cache") };
let conf = readFileSync(join(out, "hooks/default.conf.template"), "utf8")
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
const test = spawnSync("nginx", ["-t", "-p", nginxDir, "-c", join(nginxDir, "nginx.conf")], { encoding: "utf8" });
if (test.status !== 0) fail(`nginx rejected the patched config:\n${test.stderr}`);

// 5. Stub API: heartbeat succeeds, everything else answers 401.
const api = createServer((req, res) => {
  const ok = req.url.startsWith("/api/heartbeat");
  res.writeHead(ok ? 200 : 401, { "content-type": "application/json" });
  res.end(ok ? "{}" : JSON.stringify({ detail: "Not authenticated (preview stub)" }));
}).listen(apiPort, "127.0.0.1");

const nginx = spawn("nginx", ["-p", nginxDir, "-c", join(nginxDir, "nginx.conf")], { stdio: "inherit" });
const stop = () => {
  nginx.kill();
  api.close();
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
nginx.on("exit", (code) => {
  api.close();
  process.exitCode = code ?? 0;
});
console.log(`themeable: preview at http://localhost:${port}/ (themes: http://localhost:${port}/themeable/)`);
