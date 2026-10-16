#!/usr/bin/env node
// Loads the login screen for stock and every pack in both modes through the patched nginx,
// asserting each theme took effect; writes screenshots and report.md/report.json.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { get } from "node:http";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "../../lib/args.mjs";
import { loadCatalog } from "../../lib/catalog.mjs";
import { listPacks, loadPack } from "../../lib/pack.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const mod = resolve(here, "../..");
const repo = resolve(mod, "..");
const args = parseArgs();
const port = Number(args.port ?? 8199);
const base = `http://localhost:${port}`;
const out = resolve(args.out ?? join(tmpdir(), "themeable-visual"));
mkdirSync(join(out, "shots"), { recursive: true });

const SCHEMES = ["dark", "light"];
const ROUTE = "/login";
const MIN_CHANGED = 0.01;

const { chromium } = await import(pathToFileURL(join(repo, "frontend/node_modules/playwright/index.mjs")).href);
const cssReferences = loadCatalog(join(mod, "catalog")).cssReferences ?? {};
const packs = listPacks(join(mod, "packs")).map((id) => loadPack(join(mod, "packs", id)));

function waitFor(url, ms = 30000) {
  const end = Date.now() + ms;
  return new Promise((ok, fail) => {
    const tryOnce = () =>
      get(url, (res) => {
        res.resume();
        ok();
      }).on("error", () => (Date.now() > end ? fail(new Error(`preview did not start at ${url}`)) : setTimeout(tryOnce, 500)));
    tryOnce();
  });
}

const preview = spawn(process.execPath, [join(mod, "dev/preview.mjs"), "--default", "none", "--port", String(port), "--work", join(out, "preview")], {
  stdio: ["ignore", "inherit", "inherit"],
});
const stopPreview = () => preview.kill("SIGTERM");
process.on("exit", stopPreview);

const sha = (buf) => createHash("sha256").update(buf).digest("hex");
const norm = (v) => String(v).replace(/\s+/g, " ").replace(/\s*,\s*/g, ", ").trim().toLowerCase();

/** Share of pixels that differ between two PNG buffers, computed in the browser. */
async function pixelDiff(page, a, b) {
  return page.evaluate(
    async ([x, y]) => {
      const load = (src) => new Promise((r) => { const i = new Image(); i.onload = () => r(i); i.src = src; });
      const [ia, ib] = await Promise.all([load(x), load(y)]);
      const c = new OffscreenCanvas(ia.width, ia.height);
      const ctx = c.getContext("2d");
      ctx.drawImage(ia, 0, 0);
      const da = ctx.getImageData(0, 0, ia.width, ia.height).data;
      ctx.clearRect(0, 0, ia.width, ia.height);
      ctx.drawImage(ib, 0, 0);
      const db = ctx.getImageData(0, 0, ia.width, ia.height).data;
      let changed = 0;
      for (let i = 0; i < da.length; i += 4) {
        if (Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]) > 24) changed++;
      }
      return changed / (da.length / 4);
    },
    [`data:image/png;base64,${a.toString("base64")}`, `data:image/png;base64,${b.toString("base64")}`],
  );
}

const results = [];
let browser;
try {
  await waitFor(`${base}/themeable/`);
  browser = await chromium.launch(process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});

  async function capture(theme, scheme) {
    const ctx = await browser.newContext({ colorScheme: scheme, viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto(`${base}${ROUTE}?romm-theme=${theme}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(1000);
    const shot = await page.screenshot();
    writeFileSync(join(out, "shots", `${theme}-${scheme}.png`), shot);
    return { ctx, page, errors, shot };
  }

  const stock = {};
  for (const scheme of SCHEMES) {
    const c = await capture("none", scheme);
    stock[scheme] = c.shot;
    results.push({ theme: "none", scheme, failures: c.errors.map((e) => `page error: ${e}`), changed: 0 });
    await c.ctx.close();
  }

  for (const { dir, pack } of packs) {
    for (const scheme of SCHEMES) {
      const { ctx, page, errors, shot } = await capture(pack.id, scheme);
      const failures = errors.map((e) => `page error: ${e}`);

      const state = await page.evaluate(() => ({
        attr: document.documentElement.getAttribute("data-romm-theme"),
        sheet: !!document.querySelector("#themeable-css")?.sheet,
      }));
      if (state.attr !== pack.id) failures.push(`data-romm-theme is "${state.attr}"`);
      if (!state.sheet) failures.push("theme stylesheet did not load");

      const expected = { ...(pack.tokens?.common ?? {}), ...(pack.tokens?.[scheme] ?? {}) };
      const actual = await page.evaluate((names) => {
        const cs = getComputedStyle(document.documentElement);
        return Object.fromEntries(names.map((n) => [n, cs.getPropertyValue(n)]));
      }, Object.keys(expected));
      for (const [name, value] of Object.entries(expected)) {
        if (norm(actual[name]) !== norm(value)) failures.push(`${name} is "${actual[name].trim()}", expected "${value}"`);
      }

      for (const [key, rel] of Object.entries(pack.assets ?? {})) {
        const res = await page.request.get(`${base}${key}`);
        if (!res.ok()) failures.push(`${key} returned ${res.status()}`);
        else if (sha(await res.body()) !== sha(readFileSync(join(dir, rel)))) failures.push(`${key} is not the pack's file`);
        for (const ref of cssReferences[key] ?? []) {
          if (ref.atRules.length) continue;
          const value = await page.evaluate(
            ([sel, prop]) => {
              const el = document.querySelector(sel);
              return el ? getComputedStyle(el).getPropertyValue(prop) : null;
            },
            [ref.selector, ref.property],
          );
          if (value !== null && !value.includes(`/themes/${pack.id}/`)) {
            failures.push(`${ref.selector} ${ref.property} still uses stock artwork`);
          }
        }
      }

      const changed = await pixelDiff(page, stock[scheme], shot);
      const touchesVisuals = Object.keys(expected).length || Object.keys(pack.assets ?? {}).length;
      if (touchesVisuals && changed < MIN_CHANGED) failures.push(`only ${(changed * 100).toFixed(2)}% of pixels differ from stock`);

      results.push({ theme: pack.id, scheme, failures, changed });
      await ctx.close();
    }
  }
} finally {
  await browser?.close();
  stopPreview();
}

const failed = results.filter((r) => r.failures.length);
const table = [
  "| Theme | Mode | Pixels changed vs stock | Result |",
  "| --- | --- | --- | --- |",
  ...results.map((r) => `| ${r.theme} | ${r.scheme} | ${r.theme === "none" ? "baseline" : `${(r.changed * 100).toFixed(1)}%`} | ${r.failures.length ? r.failures.join("; ") : "pass"} |`),
].join("\n");
const report = [
  "## themeable visual check",
  failed.length ? `**${failed.length} of ${results.length} runs failed.**` : `**All ${results.length} runs passed** on \`${ROUTE}\`.`,
  table,
  "Screenshots are attached to the workflow run as the `themeable-visual` artifact.",
].join("\n\n");
writeFileSync(join(out, "report.md"), report + "\n");
writeFileSync(join(out, "report.json"), JSON.stringify(results, null, 2) + "\n");
console.log(readFileSync(join(out, "report.md"), "utf8"));
process.exit(failed.length ? 1 : 0);
