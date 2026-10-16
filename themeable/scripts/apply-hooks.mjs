#!/usr/bin/env node
// Applies the index.html, nginx and sw.js hooks to files from a RomM image's web root.
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { fail, parseArgs } from "../lib/args.mjs";
import { injectLoader } from "../lib/html.mjs";
import { patchNginx } from "../lib/nginx.mjs";
import { updatePrecacheRevisions } from "../lib/sw.mjs";

const args = parseArgs();
if (!args.webroot || !args.nginx || !args.out) fail("pass --webroot <dir> --nginx <template> --out <dir>");
const webroot = resolve(args.webroot);
const out = resolve(args.out);
const defaultTheme = args.default ?? "none";
mkdirSync(out, { recursive: true });

try {
  const html = injectLoader(readFileSync(join(webroot, "index.html"), "utf8"));
  writeFileSync(join(out, "index.html"), html);
  console.log("themeable: loader injected into index.html");

  writeFileSync(join(out, "default.conf.template"), patchNginx(readFileSync(resolve(args.nginx), "utf8"), defaultTheme));
  console.log(`themeable: nginx /assets block patched (default theme "${defaultTheme}")`);

  const swFile = join(webroot, "sw.js");
  if (!existsSync(swFile)) fail("no sw.js in the web root; upstream changed its service worker setup");
  {
    const changed = { "index.html": html };
    const overlay = args["root-overlay"] ? resolve(args["root-overlay"]) : null;
    if (overlay && existsSync(overlay)) {
      for (const f of readdirSync(overlay)) changed[f] = readFileSync(join(overlay, f));
    }
    const { text, updated } = updatePrecacheRevisions(readFileSync(swFile, "utf8"), changed);
    if (!updated.includes("index.html")) fail("sw.js no longer precaches index.html by revision; recheck the hook");
    writeFileSync(join(out, "sw.js"), text);
    console.log(`themeable: service worker revisions refreshed for ${updated.join(", ")}`);
  }
} catch (e) {
  fail(e.message);
}
