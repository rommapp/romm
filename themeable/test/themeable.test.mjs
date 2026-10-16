import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { diffCatalogs } from "../lib/catalog.mjs";
import { findCssReferences, scopeSelectorList } from "../lib/cssrefs.mjs";
import { injectLoader } from "../lib/html.mjs";
import { patchNginx } from "../lib/nginx.mjs";
import { applyAliases, compilePack, hexToRgbTriplet, validatePack } from "../lib/pack.mjs";
import { updatePrecacheRevisions, md5 } from "../lib/sw.mjs";
import { parseTokenCss } from "../lib/tokens.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "../..");

function tempPack(pack, files = {}) {
  const dir = mkdtempSync(join(tmpdir(), "themeable-pack-"));
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), content);
  }
  return { dir, pack: { id: "test", name: "Test", ...pack } };
}

test("parses token scopes from minified CSS", () => {
  const scopes = parseTokenCss(readFileSync(join(here, "fixtures/tokens.min.css"), "utf8"));
  assert.equal(scopes.common["--r-color-brand-primary"], "#8b74e8");
  assert.equal(scopes.dark["--r-color-bg"], "#07070f");
  assert.equal(scopes.light["--r-color-brand-primary"], "#553e98");
  assert.equal(scopes["input-key"]["--r-focus-ring-width"], "2.5px");
  assert.equal(scopes.common["--r-not-a-scope"], undefined);
});

test("parses the upstream tokens.css with every scope populated", () => {
  const scopes = parseTokenCss(readFileSync(join(repo, "frontend/src/v2/styles/tokens.css"), "utf8"));
  for (const s of ["common", "dark", "light", "input-key", "input-pad"]) {
    assert.ok(Object.keys(scopes[s]).length > 0, `scope ${s} is empty`);
  }
});

test("rejects unsafe ids, values and paths", () => {
  const bad = tempPack({
    id: "../x",
    tokens: { common: { "--r-color-bg": "red; } body { display:none" }, weird: {} },
    assets: { "/assets/../etc/passwd": "a.svg", "/assets/emulatorjs/x.js": "a.js" },
  });
  const { errors } = validatePack(bad);
  assert.ok(errors.some((e) => e.startsWith("id must match")));
  assert.ok(errors.some((e) => e.includes("value must be")));
  assert.ok(errors.some((e) => e.includes("unknown scope")));
  assert.ok(errors.some((e) => e.includes("must be an /assets/")));
  assert.ok(errors.some((e) => e.includes("can't be themed")));
});

test("checks tokens and assets against the catalog", () => {
  const p = tempPack(
    { tokens: { dark: { "--r-color-gone": "#000" } }, assets: { "/assets/new.svg": "a.svg", "/assets/logo.svg": "a.png" } },
    { "a.svg": "<svg/>", "a.png": "x" },
  );
  const { errors, warnings } = validatePack(p, { tokens: new Set(["--r-color-bg"]), assets: new Set(["/assets/logo.svg"]) });
  assert.ok(errors.some((e) => e.includes("--r-color-gone does not exist")));
  assert.ok(errors.some((e) => e.includes("same extension")));
  assert.ok(warnings.some((w) => w.includes("/assets/new.svg")));
});

test("aliases rewrite renamed tokens", () => {
  const p = tempPack({ tokens: { common: { "--r-old": "1px" } } });
  const notes = applyAliases(p.pack, { "--r-old": "--r-new" });
  assert.deepEqual(p.pack.tokens.common, { "--r-new": "1px" });
  assert.equal(notes.length, 1);
});

test("compiles scoped CSS, v1 palette and re-pointed inlined artwork", () => {
  const p = tempPack(
    {
      tokens: { common: { "--r-color-brand-primary": "#f08a4b" }, light: { "--r-color-bg": "#fff" } },
      vuetify: { dark: { primary: "#f08a4b" } },
      assets: { "/assets/bg.svg": "bg.svg" },
    },
    { "bg.svg": "<svg/>" },
  );
  assert.deepEqual(validatePack(p).errors, []);
  const refs = { "/assets/bg.svg": [{ file: "x.vue", atRules: ["@-moz-document url-prefix()"], selector: ".auth", property: "background-image", value: 'url("/assets/bg.svg")' }] };
  const { css, files, meta } = compilePack(p, { cssReferences: refs });
  assert.match(css, /:root\[data-romm-theme="test"\]\.r-v2,\n:root\[data-romm-theme="test"\] \.r-v2 \{\n {2}--r-color-brand-primary: #f08a4b;/);
  assert.match(css, /:root\[data-romm-theme="test"\]\.r-v2\.r-v2-light/);
  assert.match(css, /\.v-theme--dark \{\n {2}--v-theme-primary: 240,138,75;/);
  assert.match(css, /@-moz-document url-prefix\(\) \{\n:root\[data-romm-theme="test"\] \.auth \{\n {2}background-image: url\("\/themes\/test\/assets\/bg\.svg\?v=[0-9a-f]+"\);/);
  assert.deepEqual(files.map((f) => f.to), ["themes/test/assets/bg.svg"]);
  assert.match(meta.css, /^\/themes\/test\/theme\.css\?v=[0-9a-f]{12}$/);
});

test("finds CSS artwork references, skipping @font-face", () => {
  const css = `.a { background: url("/assets/x.svg") center; }
@font-face { src: url(/assets/f.woff2); }
@media (x) { .b, .c { background-image: url('/assets/x.svg'); } }`;
  const refs = findCssReferences(css, "f.css");
  assert.equal(refs["/assets/x.svg"].length, 2);
  assert.deepEqual(refs["/assets/x.svg"][1].atRules, ["@media (x)"]);
  assert.equal(refs["/assets/f.woff2"], undefined);
  assert.equal(scopeSelectorList(".b, html.k .c", ":root[t]"), ":root[t] .b,\n:root[t].k .c");
});

test("injects the loader once and keeps it in <head>", () => {
  const html = "<html><head><title>x</title></head><body></body></html>";
  const once = injectLoader(html);
  assert.equal(injectLoader(once), once);
  assert.ok(once.indexOf("/themeable/loader.js") < once.indexOf("</head>"));
  assert.throws(() => injectLoader("<html></html>"), /no <\/head>/);
});

test("patches the real nginx template's /assets block only", () => {
  const conf = readFileSync(join(repo, "docker/nginx/templates/default.conf.template"), "utf8");
  const patched = patchNginx(conf, "ember");
  assert.match(patched, /map \$cookie_romm_theme \$themeable_theme \{\n {4}default "ember";/);
  assert.match(patched, /location \/assets \{\n\s+add_header Cache-Control "no-cache";\n\s+add_header Vary Cookie;[\s\S]*?try_files \/themes\/\$themeable_theme\$uri \$uri \$uri\/ =404;/);
  assert.ok(patched.includes("location /assets/romm/resources/ {"), "other /assets locations stay");
  assert.throws(() => patchNginx(patched), /already patched/);
  assert.throws(() => patchNginx(conf, "../x"), /bad default theme/);
});

test("refreshes the service worker revision for changed files", () => {
  const sw = 'precacheAndRoute([{url:"index.html",revision:"aaa"},{url:"assets/x-123.js",revision:null}])';
  const { text, updated } = updatePrecacheRevisions(sw, { "index.html": "new" });
  assert.deepEqual(updated, ["index.html"]);
  assert.ok(text.includes(`{url:"index.html",revision:"${md5("new")}"}`));
});

test("hex to Vuetify triplet", () => {
  assert.equal(hexToRgbTriplet("#fff"), "255,255,255");
  assert.equal(hexToRgbTriplet("#f08a4b"), "240,138,75");
});

test("catalog diff reports removals", () => {
  const a = { tokens: { tokens: [{ name: "--r-a", defaults: { common: "1" } }, { name: "--r-b", defaults: {} }] }, assets: { files: ["/assets/x.svg"] } };
  const b = { tokens: { tokens: [{ name: "--r-a", defaults: { common: "2" } }] }, assets: { files: [] } };
  const d = diffCatalogs(a, b);
  assert.deepEqual(d.tokensRemoved, ["--r-b"]);
  assert.deepEqual(d.tokenDefaultsChanged, ["--r-a"]);
  assert.deepEqual(d.assetsRemoved, ["/assets/x.svg"]);
});

test("folder packs replace built-in ones and broken packs are reported", async () => {
  const { collectPacks } = await import("../lib/compile.mjs");
  const builtIn = mkdtempSync(join(tmpdir(), "themeable-builtin-"));
  const folder = mkdtempSync(join(tmpdir(), "themeable-folder-"));
  for (const [dir, name, source] of [[builtIn, "ember", "b"], [folder, "ember", "f"]]) {
    mkdirSync(join(dir, name));
    writeFileSync(join(dir, name, "theme.json"), JSON.stringify({ id: name, name: source }));
  }
  mkdirSync(join(folder, "broken"));
  writeFileSync(join(folder, "broken", "theme.json"), "{ nope");
  const entries = collectPacks([{ dir: builtIn, source: "built-in" }, { dir: folder, source: "folder" }]);
  assert.deepEqual(entries.map((e) => [e.name, e.source]), [["broken", "folder"], ["ember", "folder"]]);
  assert.match(entries[0].errors[0], /could not be read/);
});

test("an unreadable or invalid selection falls back to RomM's default look", async () => {
  const { readSelection } = await import("../lib/compile.mjs");
  const dir = mkdtempSync(join(tmpdir(), "themeable-sel-"));
  const file = join(dir, "themeable.json");
  assert.deepEqual(readSelection(file), { theme: "none", note: null });
  writeFileSync(file, "garbage");
  assert.equal(readSelection(file).theme, "none");
  writeFileSync(file, JSON.stringify({ theme: "../etc" }));
  assert.equal(readSelection(file).theme, "none");
  writeFileSync(file, JSON.stringify({ theme: "ember" }));
  assert.equal(readSelection(file).theme, "ember");
});

test("a selected theme that doesn't compile leaves RomM's default look in effect", async () => {
  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const out = mkdtempSync(join(tmpdir(), "themeable-out-"));
  const result = compileAll({
    entries: collectPacks([{ dir: join(here, "../packs"), source: "built-in" }]),
    catalog: { aliases: {} },
    outDir: out,
    selected: "missing",
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  assert.equal(result.effective, "none");
  assert.match(result.reason, /not installed/);
  assert.match(readFileSync(join(out, "themeable/loader.js"), "utf8"), /"default":"none"/);
});

test("patches apply to the current upstream files and the overlay doesn't collide", async () => {
  const { loadPatches, overlayFiles } = await import("../lib/source.mjs");
  for (const patch of await loadPatches(join(here, "../patches"))) {
    const original = readFileSync(join(repo, patch.file), "utf8");
    const patched = patch.apply(original);
    assert.notEqual(patched, original, `${patch.name} changed nothing`);
    assert.equal(patch.apply(patched), patched, `${patch.name} is not idempotent`);
  }
  for (const rel of overlayFiles(join(here, "../overlay"))) {
    assert.ok(!existsSync(join(repo, rel)), `${rel} exists upstream`);
  }
});

test("the overlay refuses to replace an upstream file", async () => {
  const { applyOverlay } = await import("../lib/source.mjs");
  const overlay = mkdtempSync(join(tmpdir(), "themeable-ov-"));
  const root = mkdtempSync(join(tmpdir(), "themeable-root-"));
  mkdirSync(join(overlay, "backend"));
  writeFileSync(join(overlay, "backend/main.py"), "ours");
  mkdirSync(join(root, "backend"));
  writeFileSync(join(root, "backend/main.py"), "upstream");
  assert.throws(() => applyOverlay(overlay, root), /would replace an upstream file/);
});
