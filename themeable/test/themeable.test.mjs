import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readdirSync, readFileSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { diffCatalogs } from "../lib/catalog.mjs";
import { findCssReferences, scopeSelectorList } from "../lib/cssrefs.mjs";
import { injectLoader } from "../lib/html.mjs";
import { patchNginx, SANDBOX_POLICY } from "../lib/nginx.mjs";
import { PACK_ID_PATTERN } from "../lib/client.mjs";
import { applyAliases, compilePack, hexToRgbTriplet, validatePack } from "../lib/pack.mjs";
import { updatePrecacheRevisions, md5 } from "../lib/sw.mjs";
import { folderFiles } from "../lib/packfiles.mjs";
import * as zip from "../lib/zip.mjs";
import { parseTokenCss } from "../lib/tokens.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "../..");

function tempPack(pack, files = {}) {
  const dir = mkdtempSync(join(tmpdir(), "themeable-pack-"));
  for (const [rel, content] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true });
    writeFileSync(join(dir, rel), content);
  }
  return { files: folderFiles(dir), pack: { id: "test", name: "Test", ...pack } };
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
  assert.match(patched, /map "\$arg_romm_theme:\$cookie_romm_theme" \$themeable_theme \{\n {4}default "ember";/);
  assert.match(patched, /location \/assets \{\n\s+add_header Cache-Control "no-cache";\n\s+add_header Vary Cookie;[\s\S]*?try_files \/themes\/\$themeable_theme\$uri \$uri \$uri\/ =404;/);
  assert.ok(patched.includes("location /assets/romm/resources/ {"), "other /assets locations stay");
  const sandboxed = (block) => assert.match(block, new RegExp(`Content-Security-Policy "${SANDBOX_POLICY}";\\n\\s+add_header X-Content-Type-Options nosniff;`));
  sandboxed(patched.slice(patched.indexOf("location /themes/ {")));
  sandboxed(patched.slice(patched.indexOf("location ~* \\.svg$ {")));
  sandboxed(patched.slice(patched.indexOf('location ~ "^/(favicon')));
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
  const { compileAll } = await import("../lib/compile.mjs");
  const entries = collectPacks([{ dir: builtIn, source: "built-in" }, { dir: folder, source: "folder" }]);
  assert.deepEqual(entries.map((e) => [e.name, e.source]), [["broken", "folder"], ["ember", "folder"]]);
  const { packs } = compileAll({
    entries,
    catalog: { aliases: {} },
    outDir: mkdtempSync(join(tmpdir(), "themeable-out-")),
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  assert.match(packs[0].errors[0], /could not be read/);
  assert.equal(packs[1].name, "f");
});

test("an unreadable or invalid selection falls back to RomM's default look", async () => {
  const { readSelection } = await import("../lib/compile.mjs");
  const dir = mkdtempSync(join(tmpdir(), "themeable-sel-"));
  const file = join(dir, "themeable.json");
  assert.deepEqual(readSelection(file), { theme: "none", hidden: [], random: { stock: false, built_in: true, accessibility: true }, names: {}, note: null });
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

test("root docker-compose.yml pins the image to ROMM_VERSION", () => {
  const version = readFileSync(join(here, "..", "ROMM_VERSION"), "utf8").trim();
  const compose = readFileSync(join(here, "..", "..", "docker-compose.yml"), "utf8");
  const tags = [...compose.matchAll(/(?:romm-themeable:|ROMM_VERSION: )(\S+)/g)].map((m) => m[1]);
  assert.ok(tags.length >= 2, "image tag and build arg are present");
  for (const tag of tags) assert.equal(tag, version);
  assert.match(compose, /^\s+- \/path\/to\/themes:\/romm\/themes /m, "themes volume is mapped");
});

test("a malformed pack disables only itself", async () => {
  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const folder = mkdtempSync(join(tmpdir(), "themeable-packs-"));
  const shapes = {
    "null-scope": { tokens: { common: null } },
    "string-scope": { tokens: { dark: "red" } },
    "null-tokens": { tokens: null },
    "null-vuetify-mode": { vuetify: { dark: null } },
    "fonts-object": { fonts: { family: "x" } },
    "assets-list": { assets: ["/assets/isotipo.svg"] },
    "pwa-string": { pwa: "#fff" },
  };
  for (const [id, extra] of Object.entries(shapes)) {
    mkdirSync(join(folder, id));
    writeFileSync(join(folder, id, "theme.json"), JSON.stringify({ id, name: id, ...extra }));
  }
  mkdirSync(join(folder, "not-an-object"));
  writeFileSync(join(folder, "not-an-object", "theme.json"), "null");
  const out = mkdtempSync(join(tmpdir(), "themeable-out-"));
  const result = compileAll({
    entries: collectPacks([
      { dir: join(here, "../packs"), source: "built-in" },
      { dir: folder, source: "folder" },
    ]),
    catalog: { aliases: { "--r-old": "--r-new" } },
    outDir: out,
    selected: "null-scope",
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  for (const id of [...Object.keys(shapes), "not-an-object"]) {
    const status = result.packs.find((p) => p.id === id);
    assert.equal(status.valid, false, id);
    assert.ok(status.errors.length, `${id} reports why`);
    assert.ok(!existsSync(join(out, "themes", id)), `${id} leaves no output`);
  }
  assert.ok(result.packs.find((p) => p.id === "ember").valid, "built-in pack still compiles");
  assert.ok(existsSync(join(out, "themes/ember/theme.css")));
  assert.equal(result.effective, "none");
  assert.match(result.reason, /has errors/);
});

test("reserved ids are rejected by the validator and the schema alike", () => {
  const schema = JSON.parse(readFileSync(join(here, "..", "schema", "theme.schema.json"), "utf8"));
  const schemaReserved = schema.properties.id.not.enum;
  for (const id of ["none", "default", "random", "index", "stock"]) {
    assert.ok(schemaReserved.includes(id), `schema reserves ${id}`);
    const { errors } = validatePack({ files: folderFiles(tmpdir()), pack: { id, name: id } });
    assert.ok(errors.some((e) => e.includes("reserved")), `validator reserves ${id}`);
  }
  assert.equal(schema.properties.id.pattern, `^${PACK_ID_PATTERN}$`, "the schema uses the shared id pattern");
});

test("packs can only publish images and fonts, and no SVG that runs code", () => {
  const html = tempPack({ assets: { "/assets/payload.html": "payload.html" } }, { "payload.html": "<script>alert(1)</script>" });
  assert.ok(validatePack(html).errors.some((e) => e.includes("only replace images, fonts and stylesheets")));
  for (const svg of [
    '<svg><script>alert(1)</script></svg>',
    '<svg onload="alert(1)"></svg>',
    '<svg><a href="javascript:alert(1)"><text>x</text></a></svg>',
    '<svg><foreignObject><iframe src="x"/></foreignObject></svg>',
  ]) {
    const pack = tempPack(
      { assets: { "/assets/logo.svg": "logo.svg" }, covers: { missing: ["cover.svg"] } },
      { "logo.svg": svg, "cover.svg": svg },
    );
    const errors = validatePack(pack).errors.filter((e) => e.includes("scripts, event handlers"));
    assert.equal(errors.length, 2, `refuses ${svg} as artwork and as a cover`);
  }
  const plain = tempPack({ assets: { "/assets/logo.svg": "logo.svg" } }, { "logo.svg": '<svg><rect width="4" height="4" opacity="0.5"/></svg>' });
  assert.deepEqual(validatePack(plain).errors, []);
});

test("browser files read shared values from the manifest instead of declaring them", async () => {
  const { CLIENT } = await import("../lib/client.mjs");
  const files = [
    "loader/loader.js",
    "picker/index.html",
    "overlay/frontend/src/v2/components/Settings/BrandingSection.vue",
    "overlay/frontend/src/v2/components/Settings/BrandingArtwork.vue",
    "overlay/frontend/src/v2/components/Settings/BrandingRandomArtwork.vue",
    "overlay/frontend/src/v2/composables/useArtworkCycle/index.ts",
    "overlay/frontend/src/v2/components/Settings/BrandingUpload.vue",
    "overlay/frontend/src/v2/composables/usePackUpload/index.ts",
    "overlay/frontend/src/services/api/themeable.ts",
  ];
  const values = Object.values(CLIENT).flat();
  for (const file of files) {
    const text = readFileSync(join(here, "..", file), "utf8");
    for (const value of values) {
      for (const q of ['"', "'", "`"]) {
        assert.ok(!text.includes(q + value + q), `${file} declares ${q}${value}${q}; read it from manifest.client`);
      }
    }
  }
});

test("the compiled manifest carries the shared client values", async () => {
  const { CLIENT } = await import("../lib/client.mjs");
  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const out = mkdtempSync(join(tmpdir(), "themeable-out-"));
  compileAll({
    entries: collectPacks([{ dir: join(here, "../packs"), source: "built-in" }]),
    catalog: { aliases: {} },
    outDir: out,
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  const manifest = JSON.parse(readFileSync(join(out, "themes/index.json"), "utf8"));
  assert.deepEqual(manifest.client, { ...CLIENT });
  assert.ok(readFileSync(join(out, "themeable/loader.js"), "utf8").includes(JSON.stringify(CLIENT.storage_key)));
});

test("docs/theme.example.json is current and sets every option validly", async () => {
  const { buildExample, parseCoverArt, parseThemeColor, parseVuetifyThemes } = await import("../lib/example.mjs");
  const { loadCatalog } = await import("../lib/catalog.mjs");
  const { ROOT_FILES } = await import("../lib/pack.mjs");
  const frontend = join(here, "..", "..", "frontend");
  const readJson = (f) => JSON.parse(readFileSync(join(here, "..", f), "utf8"));
  const expected = buildExample({
    tokenCatalog: readJson("catalog/tokens.json"),
    assetCatalog: readJson("catalog/assets.json"),
    vuetify: parseVuetifyThemes(readFileSync(join(frontend, "src/styles/themes.ts"), "utf8")),
    themeColor: parseThemeColor(readFileSync(join(frontend, "index.html"), "utf8")),
    coverArt: parseCoverArt(readFileSync(join(frontend, "src/v2/tokens/index.ts"), "utf8")),
  });
  const example = readJson("docs/theme.example.json");
  assert.deepEqual(example, expected, "run `npm run example`");

  const schema = readJson("schema/theme.schema.json");
  assert.deepEqual(Object.keys(example).sort(), Object.keys(schema.properties).sort(), "every top-level option is set");
  assert.deepEqual(Object.keys(example.rootFiles).sort(), [...ROOT_FILES].sort());
  const catalog = loadCatalog(join(here, "..", "catalog"));
  assert.equal(Object.keys(example.assets).length, catalog.assets.size, "every replaceable file is listed");
  assert.equal(new Set(Object.values(example.tokens).flatMap(Object.keys)).size, catalog.tokens.size, "every token is listed");
  const { errors } = validatePack({ files: folderFiles(tmpdir()), pack: example }, catalog);
  assert.deepEqual(errors.filter((e) => !/missing file/.test(e)), []);
});

test("Branding's preview slots name real stock files, and every pack's favicons are published", async () => {
  const { PREVIEW_SLOTS, COOKIE, STOCK_ID } = await import("../lib/client.mjs");
  const { loadCatalog } = await import("../lib/catalog.mjs");
  const { ROOT_FILES } = await import("../lib/pack.mjs");
  const catalog = loadCatalog(join(here, "..", "catalog"));
  for (const [slot, url] of Object.entries(PREVIEW_SLOTS)) {
    assert.ok(catalog.assets.has(url) || ROOT_FILES.has(url), `${slot}: ${url} is not a stock file`);
  }

  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const out = mkdtempSync(join(tmpdir(), "themeable-out-"));
  const result = compileAll({
    entries: collectPacks([{ dir: join(here, "../packs"), source: "built-in" }]),
    catalog: { aliases: {} },
    outDir: out,
    selected: STOCK_ID,
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  for (const c of result.compiled) {
    for (const f of c.rootFiles) assert.ok(existsSync(join(out, "themes", c.meta.id, "root", f.to)), `${c.meta.id} ${f.to}`);
  }
  assert.ok(!existsSync(join(out, "themeable", "root")), "no favicons are served by default for the stock look");

  const conf = readFileSync(join(here, "../../docker/nginx/templates/default.conf.template"), "utf8");
  const patched = patchNginx(conf);
  assert.match(patched, new RegExp(`map "\\$arg_${COOKIE}:\\$cookie_${COOKIE}" \\$themeable_root \\{`));
  assert.match(patched, /add_header Vary Cookie;[^}]*try_files \$themeable_root\$uri \$uri =404;/);
});

// Runs the real loader against a stub page; `seed` makes Math.random repeatable.
function runLoader(manifest, { cookie = "", stored = null, search = "", seed = 1 } = {}) {
  const storage = new Map(stored ? [[manifest.client.storage_key, stored]] : []);
  const attrs = {};
  const doc = {
    cookie,
    documentElement: { setAttribute: (k, v) => (attrs[k] = v) },
    getElementById: () => null,
    createElement: () => ({ setAttribute() {} }),
    head: { appendChild() {} },
    querySelector: () => null,
  };
  let state = seed;
  const ctx = vm.createContext({
    document: doc,
    location: { search, protocol: "http:", href: `http://romm.test/${search}`, origin: "http://romm.test" },
    URL,
    URLSearchParams,
    MutationObserver: class {
      observe() {}
    },
    // mulberry32
    seeded: () => {
      state = (state + 0x6d2b79f5) | 0;
      let t = Math.imul(state ^ (state >>> 15), 1 | state);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    },
  });
  ctx.window = ctx;
  ctx.addEventListener = () => {};
  ctx.localStorage = { getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: (k) => storage.delete(k) };
  vm.runInContext("Math.random = seeded;", ctx);
  const source = readFileSync(join(here, "../loader/loader.js"), "utf8");
  vm.runInContext(source.replace("__THEMEABLE_MANIFEST__", JSON.stringify(manifest)), ctx);
  const cookieId = doc.cookie.match(new RegExp(`${manifest.client.cookie}=([a-z0-9-]+)`))?.[1] ?? null;
  return { theme: attrs[manifest.client.theme_attribute], cookie: cookieId, stored: storage.get(manifest.client.storage_key) ?? null };
}

test("Random draws one usable pack per load, never the one this browser showed last", async () => {
  const { CLIENT, RANDOM_ID, STOCK_ID } = await import("../lib/client.mjs");
  const themes = ["aurora", "ember", "neon"].map((id) => ({ id, name: id, css: `/themes/${id}/theme.css` }));
  const manifest = { default: RANDOM_ID, client: CLIENT, themes, random: { ids: themes.map((t) => t.id) } };
  const counts = { aurora: 0, ember: 0, neon: 0 };
  for (let seed = 1; seed <= 300; seed++) {
    const r = runLoader(manifest, { cookie: `${CLIENT.cookie}=ember`, seed });
    assert.notEqual(r.theme, "ember");
    assert.equal(r.cookie, r.theme, "nginx gets the drawn pack, not the reserved id");
    assert.equal(r.stored, null, "following the server's Random stores nothing");
    counts[r.theme]++;
  }
  assert.ok(counts.aurora > 120 && counts.neon > 120, `uneven draw: ${JSON.stringify(counts)}`);
  assert.deepEqual(runLoader(manifest, { seed: 7 }), runLoader(manifest, { seed: 7 }), "the same seed draws the same pack");

  const one = { ...manifest, themes: themes.slice(1, 2), random: { ids: ["ember"] } };
  assert.equal(runLoader(one, { cookie: `${CLIENT.cookie}=ember` }).theme, "ember", "a single pack is drawn even if shown last");
  assert.equal(runLoader({ ...manifest, themes: [], random: { ids: [] } }, { stored: RANDOM_ID }).theme, STOCK_ID, "nothing to draw from means RomM's look");
});

test("a browser can choose Random for itself, and a Random preview leaves the cookie alone", async () => {
  const { CLIENT, RANDOM_ID } = await import("../lib/client.mjs");
  const themes = ["aurora", "ember"].map((id) => ({ id, name: id, css: `/themes/${id}/theme.css` }));
  const manifest = { default: "ember", client: CLIENT, themes, random: { ids: themes.map((t) => t.id) } };
  const chosen = runLoader(manifest, { search: `?${CLIENT.url_param}=${RANDOM_ID}`, cookie: `${CLIENT.cookie}=ember` });
  assert.equal(chosen.stored, RANDOM_ID);
  assert.equal(chosen.theme, "aurora");
  assert.equal(chosen.cookie, "aurora");
  assert.equal(runLoader(manifest, { stored: RANDOM_ID, cookie: `${CLIENT.cookie}=aurora` }).theme, "ember");
  const preview = runLoader(manifest, { search: `?${CLIENT.preview_param}=${RANDOM_ID}`, cookie: `${CLIENT.cookie}=aurora` });
  assert.equal(preview.theme, "ember");
  assert.equal(preview.cookie, "aurora", "a preview tab never changes the shared cookie");
});

test("Random as the server's theme compiles, and falls back to RomM's look with nothing to draw", async () => {
  const { RANDOM_ID } = await import("../lib/client.mjs");
  const { collectPacks, compileAll, readSelection } = await import("../lib/compile.mjs");
  const dir = mkdtempSync(join(tmpdir(), "themeable-sel-"));
  writeFileSync(join(dir, "themeable.json"), JSON.stringify({ theme: RANDOM_ID }));
  assert.equal(readSelection(join(dir, "themeable.json")).theme, RANDOM_ID);
  const compile = (entries) =>
    compileAll({
      entries,
      catalog: { aliases: {} },
      outDir: mkdtempSync(join(tmpdir(), "themeable-out-")),
      selected: RANDOM_ID,
      loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
      pickerFile: join(here, "../picker/index.html"),
    });
  const withPacks = compile(collectPacks([{ dir: join(here, "../packs"), source: "built-in" }]));
  assert.equal(withPacks.effective, RANDOM_ID);
  assert.equal(withPacks.reason, null);
  const empty = compile([]);
  assert.equal(empty.effective, "none");
  assert.match(empty.reason, /nothing to draw from/);
});

// Archives for the zip tests; `patch` swaps same-length bytes to forge what writeZip refuses to write.
function tempZip(files, patch = []) {
  const file = join(mkdtempSync(join(tmpdir(), "themeable-zip-")), "pack.zip");
  zip.writeZip(file, Object.entries(files).map(([name, data]) => ({ name, data: Buffer.from(data) })));
  let buf = readFileSync(file);
  for (const [from, to] of patch) buf = Buffer.from(buf.toString("latin1").split(from).join(to), "latin1");
  writeFileSync(file, buf);
  return file;
}

test("zip archives round-trip and every limit is checked before inflating", () => {
  const file = tempZip({ "theme.json": "{}", "assets/a.svg": "<svg/>".repeat(40) });
  const z = zip.openZip(file);
  assert.deepEqual(z.names, ["theme.json", "assets/a.svg"]);
  assert.equal(z.read("assets/a.svg").toString(), "<svg/>".repeat(40));
  z.close();

  const limits = { ...zip.LIMITS };
  assert.throws(() => zip.openZip(file, { ...limits, entries: 1 }), /2 entries; the limit is 1/);
  assert.throws(() => zip.openZip(file, { ...limits, file: 100 }), /"assets\/a.svg" is .* the limit is .* per file/);
  assert.throws(() => zip.openZip(file, { ...limits, total: 200 }), /more than .* uncompressed/);
  const bomb = tempZip({ "zeros.bin": Buffer.alloc(1024 * 1024) });
  assert.throws(() => zip.openZip(bomb), /compresses more than 100:1/);
  for (const name of ["MAX_ENTRIES", "MAX_TOTAL_BYTES", "MAX_FILE_BYTES", "MAX_RATIO"]) assert.ok(zip[name] > 0, name);
});

test("malformed archives are refused with the reason", () => {
  const ok = { "aa/x.svg": "<svg/>", "b.svg": "<svg/>" };
  const expectations = [
    [tempZip(ok, [["aa/x.svg", "../x.svg"]]), /leaves the archive/],
    [tempZip(ok, [["aa/x.svg", "/a/x.svg"]]), /absolute path/],
    [tempZip(ok, [["aa/x.svg", "aa\\x.svg"]]), /backslash/],
    [tempZip({ "a.svg": "1", "b.svg": "2" }, [["b.svg", "a.svg"]]), /appears more than once/],
  ];
  for (const [file, reason] of expectations) assert.throws(() => zip.openZip(file), reason);

  const good = readFileSync(tempZip({ "a.txt": "hello" }));
  const write = (buf) => {
    const f = join(mkdtempSync(join(tmpdir(), "themeable-zip-")), "x.zip");
    writeFileSync(f, buf);
    return f;
  };
  const central = good.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02]));
  const encrypted = Buffer.from(good);
  encrypted.writeUInt16LE(encrypted.readUInt16LE(central + 8) | 1, central + 8);
  assert.throws(() => zip.openZip(write(encrypted)), /encrypted/);
  const method = Buffer.from(good);
  method.writeUInt16LE(12, central + 10);
  assert.throws(() => zip.openZip(write(method)), /compression method 12/);
  assert.throws(() => zip.openZip(write(good.subarray(0, good.length - 30))), /not a zip archive|truncated|damaged/);
  assert.throws(() => zip.openZip(write(good.subarray(10))), /truncated|damaged|not a zip/);
  const corrupt = Buffer.from(good);
  corrupt[30 + "a.txt".length] ^= 0xff;
  assert.throws(() => zip.openZip(write(corrupt)).read("a.txt"), /damaged|decompressed/);
  assert.throws(() => zip.openZip(write(Buffer.from("not a zip at all, just text"))), /not a zip archive/);
});

// Zips a built-in pack folder, optionally under `prefix` and with extra entries.
function zipBuiltIn(id, out, { prefix = "", extra = {} } = {}) {
  const dir = join(here, "../packs", id);
  const files = folderFiles(dir)
    .list()
    .map((rel) => ({ name: prefix + rel, data: readFileSync(join(dir, rel)) }));
  for (const [name, data] of Object.entries(extra)) files.push({ name, data: Buffer.from(data) });
  zip.writeZip(join(out, `${id}.zip`), files);
}

async function compileFolder(folder, reuse = null) {
  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const outDir = mkdtempSync(join(tmpdir(), "themeable-out-"));
  const result = compileAll({
    entries: collectPacks([{ dir: folder, source: "folder" }]),
    catalog: { aliases: {} },
    outDir,
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
    reuse,
  });
  return { ...result, outDir, status: (id) => result.packs.find((p) => p.id === id) };
}

test("archived packs compile like folders, at the root or inside one top-level folder", async () => {
  const folder = mkdtempSync(join(tmpdir(), "themeable-zips-"));
  zipBuiltIn("neon", folder);
  zipBuiltIn("aurora", folder, { prefix: "aurora/", extra: { "__MACOSX/aurora/._theme.json": "x", "aurora/.DS_Store": "x" } });
  const r = await compileFolder(folder);
  for (const id of ["neon", "aurora"]) {
    assert.equal(r.status(id).valid, true, `${id}: ${r.status(id).errors}`);
    assert.equal(r.status(id).format, "zip");
  }
  const original = readFileSync(join(here, "../packs/neon/assets/isotipo.svg"));
  assert.deepEqual(readFileSync(join(r.outDir, "themes/neon/assets/isotipo.svg")), original);
  assert.ok(existsSync(join(r.outDir, "themes/aurora/root/favicon-32x32.png")));
  assert.deepEqual(readdirSync(folder).sort(), ["aurora.zip", "neon.zip"], "nothing is unpacked into the themes folder");
});

test("archives that escape, nest or mislabel a pack are refused for that pack only", async () => {
  const folder = mkdtempSync(join(tmpdir(), "themeable-zips-"));
  const theme = (id, extra = {}) => JSON.stringify({ id, name: id, ...extra });
  zip.writeZip(join(folder, "escape.zip"), [
    { name: "theme.json", data: Buffer.from(theme("escape", { assets: { "/assets/isotipo.svg": "../../etc/passwd.svg" } })) },
  ]);
  const inner = join(mkdtempSync(join(tmpdir(), "themeable-inner-")), "nested.zip");
  zip.writeZip(inner, [{ name: "theme.json", data: Buffer.from(theme("nested")) }]);
  zip.writeZip(join(folder, "nested.zip"), [{ name: "nested.zip", data: readFileSync(inner) }]);
  zip.writeZip(join(folder, "renamed.zip"), [{ name: "theme.json", data: Buffer.from(theme("other")) }]);
  zip.writeZip(join(folder, "two-tops.zip"), [
    { name: "a/theme.json", data: Buffer.from(theme("two-tops")) },
    { name: "b/readme.txt", data: Buffer.from("x") },
  ]);
  writeFileSync(join(folder, "truncated.zip"), readFileSync(join(folder, "renamed.zip")).subarray(0, 40));
  zipBuiltIn("ember", folder);
  mkdirSync(join(folder, "ember"));
  writeFileSync(join(folder, "ember", "theme.json"), theme("ember"));

  const r = await compileFolder(folder);
  assert.match(r.status("escape").errors.join(), /source must be a path inside the pack/);
  assert.match(r.status("nested").errors.join(), /theme.json must be at the archive's root/);
  assert.match(r.status("renamed").errors.join(), /must match its file name "renamed.zip"/);
  assert.match(r.status("two-tops").errors.join(), /one top-level folder/);
  assert.match(r.status("truncated").errors.join(), /the archive could not be read/);
  assert.equal(r.status("ember").valid, true, "the archive wins over a folder with the same id");
  assert.match(r.status("ember").warnings.join(), /folder ember\/ is ignored/);
  assert.equal(r.packs.filter((p) => p.id === "ember").length, 1);
});

test("a compile reuses an unchanged archive and rereads one whose size or time changed", async () => {
  const folder = mkdtempSync(join(tmpdir(), "themeable-zips-"));
  zipBuiltIn("neon", folder);
  const file = join(folder, "neon.zip");
  // Whole seconds survive utimes exactly.
  const mtime = 1_700_000_000;
  utimesSync(file, mtime, mtime);
  const first = await compileFolder(folder, { key: "k1", dir: null, packs: {} });
  assert.equal(first.status("neon").valid, true);

  // Same size and time, unreadable content: only a reused build can still be valid.
  writeFileSync(file, Buffer.alloc(statSync(file).size));
  utimesSync(file, mtime, mtime);
  const reused = await compileFolder(folder, { key: "k1", dir: first.outDir, packs: first.cache });
  assert.equal(reused.status("neon").valid, true);
  assert.ok(existsSync(join(reused.outDir, "themes/neon/theme.css")));

  const newCompiler = await compileFolder(folder, { key: "k2", dir: first.outDir, packs: first.cache });
  assert.equal(newCompiler.status("neon").valid, false, "a different compiler key rereads the archive");
  utimesSync(file, new Date(), new Date());
  const touched = await compileFolder(folder, { key: "k1", dir: first.outDir, packs: first.cache });
  assert.match(touched.status("neon").errors.join(), /the archive could not be read/);
});

test("zip-packs archives the built-in packs, which compile exactly as their folders do", async () => {
  const { spawnSync } = await import("node:child_process");
  const out = join(mkdtempSync(join(tmpdir(), "themeable-zipped-")), "packs");
  const run = spawnSync(process.execPath, [join(here, "../scripts/zip-packs.mjs"), "--out", out], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr);
  const zipped = await compileFolder(out);
  const folders = await compileFolder(join(here, "../packs"));
  assert.ok(zipped.packs.every((p) => p.valid && p.format === "zip"));
  assert.deepEqual(
    zipped.compiled.map((c) => [c.meta.id, c.hash]),
    folders.compiled.map((c) => [c.meta.id, c.hash]),
  );
  const refused = spawnSync(process.execPath, [join(here, "../scripts/zip-packs.mjs"), "--out", join(here, "..")], { encoding: "utf8" });
  assert.notEqual(refused.status, 0, "an --out holding the packs is refused");
});

// Runs scripts/runtime.mjs against a scratch themes folder, as the container and the backend do.
async function runtime(themes, runtimeDir, args = [], env = {}) {
  const { spawnSync } = await import("node:child_process");
  const r = spawnSync(process.execPath, [join(here, "../scripts/runtime.mjs"), ...args], {
    encoding: "utf8",
    env: { ...process.env, THEMEABLE_PACKS_PATH: themes, THEMEABLE_RUNTIME_DIR: runtimeDir, ...env },
  });
  return { code: r.status, status: JSON.parse(r.stdout.trim().split("\n").at(-1)) };
}

test("folder packs in the themes folder are converted to archives on every run", async () => {
  const { cpSync } = await import("node:fs");
  const root = mkdtempSync(join(tmpdir(), "themeable-convert-"));
  const themes = join(root, "themes");
  const rt = join(root, "runtime");
  mkdirSync(themes);
  cpSync(join(here, "../packs/ember"), join(themes, "mine"), { recursive: true });
  const minePack = JSON.parse(readFileSync(join(themes, "mine/theme.json"), "utf8"));
  writeFileSync(join(themes, "mine/theme.json"), JSON.stringify({ ...minePack, id: "mine", name: "Mine" }));
  mkdirSync(join(themes, "broken"));
  writeFileSync(join(themes, "broken/theme.json"), JSON.stringify({ id: "broken", name: "Broken", extraCss: "gone.css" }));
  zipBuiltIn("neon", themes);
  mkdirSync(join(themes, "neon"));
  writeFileSync(join(themes, "neon/theme.json"), JSON.stringify({ id: "neon", name: "Old neon folder" }));

  const first = await runtime(themes, rt);
  assert.equal(first.code, 0, first.status.error);
  assert.deepEqual(readdirSync(themes).sort(), [".converted", "broken.zip", "mine.zip", "neon.zip"]);
  assert.deepEqual(readdirSync(join(themes, ".converted")).sort(), ["broken", "mine", "neon"], "every folder is kept, untouched");
  assert.ok(existsSync(join(themes, ".converted/mine/assets/isotipo.svg")));
  const status = (id) => first.status.packs.find((p) => p.id === id);
  assert.deepEqual([status("mine").format, status("mine").valid, status("mine").name], ["zip", true, "Mine"]);
  assert.equal(status("broken").valid, false, "a broken folder converts to a broken archive, with its problem shown");
  assert.match(first.status.notes.join(), /"mine" was converted to mine.zip/);
  assert.match(first.status.notes.join(), /folder neon\/ was moved .* because neon.zip is installed/);

  mkdirSync(join(themes, "late"));
  writeFileSync(join(themes, "late/theme.json"), JSON.stringify({ id: "late", name: "Late" }));
  const again = await runtime(themes, rt, ["--select", "late"]);
  assert.equal(again.status.effective, "late", "a folder added later is converted before the change is made");
  assert.ok(existsSync(join(themes, "late.zip")));
  for (const [args, reason] of [[["--convert", "mine"], null], [["--delete", "none"], /not a pack that can be changed/]]) {
    const r = await runtime(themes, rt, args);
    if (reason) assert.match(r.status.error, reason);
    else assert.equal(r.code, 0, "--convert is gone; the run is a plain recompile");
  }
});

// A pack archive built from a built-in pack under a new id and name, for upload tests.
function packArchive(dir, id, name, from = "ember", extra = {}) {
  const src = folderFiles(join(here, "../packs", from));
  const file = join(dir, `${id}-upload.zip`);
  zip.writeZip(
    file,
    src.list().map((n) => ({
      name: n,
      data: n === "theme.json" ? Buffer.from(JSON.stringify({ ...JSON.parse(src.read(n)), id, name, ...extra })) : src.read(n),
    })),
  );
  return file;
}

function manageSetup() {
  const root = mkdtempSync(join(tmpdir(), "themeable-manage-"));
  const themes = join(root, "themes");
  mkdirSync(themes);
  return { root, themes, rt: join(root, "runtime"), uploads: mkdtempSync(join(tmpdir(), "themeable-uploads-")) };
}

test("--validate-archive reports on an upload without touching the themes folder", async () => {
  const { themes, rt, uploads } = manageSetup();
  const { spawnSync } = await import("node:child_process");
  const validate = (file) => {
    const r = spawnSync(process.execPath, [join(here, "../scripts/runtime.mjs"), "--validate-archive", file], {
      encoding: "utf8",
      env: { ...process.env, THEMEABLE_PACKS_PATH: themes, THEMEABLE_RUNTIME_DIR: rt },
    });
    return { code: r.status, report: JSON.parse(r.stdout) };
  };
  const good = validate(packArchive(uploads, "dusk", "Dusk"));
  assert.deepEqual([good.code, good.report.ok, good.report.id, good.report.name, good.report.existing], [0, true, "dusk", "Dusk", null]);
  assert.equal(validate(packArchive(uploads, "neon", "Neon 2")).report.existing, "built-in");
  const bad = validate(packArchive(uploads, "bad", "Bad", "ember", { assets: { "/assets/isotipo.svg": "../x.svg" } }));
  assert.equal(bad.code, 1);
  assert.match(bad.report.errors.join(), /source must be a path inside the pack/);
  writeFileSync(join(uploads, "junk.zip"), "not a zip");
  assert.match(validate(join(uploads, "junk.zip")).report.errors.join(), /the archive could not be read: not a zip archive/);
  assert.deepEqual(readdirSync(themes), []);
});

test("an upload installs as <id>.zip, replaces only with --replace and never a built-in", async () => {
  const { themes, rt, uploads } = manageSetup();
  const added = await runtime(themes, rt, ["--install", packArchive(uploads, "dusk", "Dusk")]);
  assert.equal(added.code, 0, added.status.error);
  assert.deepEqual(readdirSync(themes), ["dusk.zip"]);
  const dusk = added.status.packs.find((p) => p.id === "dusk");
  assert.deepEqual([dusk.valid, dusk.format, dusk.name], [true, "zip", "Dusk"]);
  assert.match(added.status.notes.join(), /"Dusk" was added as "dusk"/);

  const again = await runtime(themes, rt, ["--install", packArchive(uploads, "dusk", "Dusk 2")]);
  assert.match(again.status.error, /already installed; confirm to replace it/);
  const replaced = await runtime(themes, rt, ["--install", packArchive(uploads, "dusk", "Dusk 2"), "--replace"]);
  assert.equal(replaced.status.packs.find((p) => p.id === "dusk").name, "Dusk 2");

  assert.match((await runtime(themes, rt, ["--install", packArchive(uploads, "neon", "Mine")])).status.error, /built-in pack and can't be replaced/);
  const broken = packArchive(uploads, "dusk", "Broken Dusk", "ember", { extraCss: "missing.css" });
  assert.match((await runtime(themes, rt, ["--install", broken, "--replace"])).status.error, /can't be installed: extraCss/);
  assert.equal((await runtime(themes, rt)).status.packs.find((p) => p.id === "dusk").name, "Dusk 2", "a refused replace keeps the old pack");
  assert.deepEqual(readdirSync(themes), ["dusk.zip"], "and leaves nothing staged");
});

test("rename rewrites the archive's name and keeps the id; delete removes or hides", async () => {
  const { themes, rt, uploads } = manageSetup();
  await runtime(themes, rt, ["--install", packArchive(uploads, "dusk", "Dusk")]);
  await runtime(themes, rt, ["--select", "dusk"]);

  const renamed = await runtime(themes, rt, ["--rename", "dusk", "--name", "  Evening  "]);
  assert.equal(renamed.code, 0, renamed.status.error);
  assert.equal(renamed.status.packs.find((p) => p.id === "dusk").name, "Evening");
  assert.equal(renamed.status.effective, "dusk", "the server theme keeps working");
  for (const [args, reason] of [
    [["--rename", "none", "--name", "X"], /not a pack that can be changed/],
    [["--rename", "dusk", "--name", " "], /name is required/],
    [["--rename", "dusk", "--name", "x".repeat(81)], /at most 80 characters/],
    [["--delete", "none"], /not a pack that can be changed/],
    [["--delete", "nothing-here"], /there is no pack "nothing-here"/],
  ]) {
    assert.match((await runtime(themes, rt, args)).status.error, reason, args.join(" "));
  }

  const deleted = await runtime(themes, rt, ["--delete", "dusk"]);
  assert.equal(deleted.code, 0, deleted.status.error);
  assert.deepEqual(readdirSync(themes), ["themeable.json"]);
  assert.equal(deleted.status.selected, "none", "deleting the server theme falls back to RomM default");
  assert.ok(!deleted.status.packs.some((p) => p.id === "dusk"));

  await runtime(themes, rt, ["--select", "neon"]);
  const hidden = await runtime(themes, rt, ["--delete", "neon"]);
  assert.deepEqual(hidden.status.hidden, ["neon"]);
  assert.equal(hidden.status.selected, "none");
  assert.ok(!hidden.status.packs.some((p) => p.id === "neon"), "a hidden built-in is not compiled");
  assert.deepEqual(JSON.parse(readFileSync(join(themes, "themeable.json"), "utf8")).hidden, ["neon"]);
  assert.ok(!(await runtime(themes, rt)).status.packs.some((p) => p.id === "neon"), "and stays hidden across restarts");
  const restored = await runtime(themes, rt, ["--restore-built-ins"]);
  assert.deepEqual(restored.status.hidden, []);
  assert.ok(restored.status.packs.find((p) => p.id === "neon").valid);
});

test("a pack change that fails keeps the previous build live", { skip: process.getuid?.() === 0 && "root ignores folder permissions" }, async () => {
  const { chmodSync, readlinkSync } = await import("node:fs");
  const { themes, rt, uploads } = manageSetup();
  await runtime(themes, rt, ["--install", packArchive(uploads, "dusk", "Dusk")]);
  const live = readlinkSync(join(rt, "current"));
  chmodSync(themes, 0o555);
  try {
    const failed = await runtime(themes, rt, ["--delete", "dusk"]);
    assert.notEqual(failed.code, 0);
    assert.equal(readlinkSync(join(rt, "current")), live, "the build that still has dusk keeps serving");
    assert.deepEqual(readdirSync(join(rt, "builds")), [basename(live)], "and the failed build is removed");
  } finally {
    chmodSync(themes, 0o755);
  }
  assert.ok(existsSync(join(themes, "dusk.zip")));
});

test("the schema and the validator share the pack name limit", async () => {
  const { PACK_NAME_MAX } = await import("../lib/pack.mjs");
  const schema = JSON.parse(readFileSync(join(here, "../schema/theme.schema.json"), "utf8"));
  assert.equal(schema.properties.name.maxLength, PACK_NAME_MAX);
});

test("built-in packs are renamed through themeable.json and can get their name back", async () => {
  const { themes, rt } = manageSetup();
  const renamed = await runtime(themes, rt, ["--rename", "neon", "--name", "Neon Nights"]);
  assert.equal(renamed.code, 0, renamed.status.error);
  const neon = renamed.status.packs.find((p) => p.id === "neon");
  assert.deepEqual([neon.name, neon.default_name], ["Neon Nights", "Neon"]);
  assert.deepEqual(JSON.parse(readFileSync(join(themes, "themeable.json"), "utf8")).names, { neon: "Neon Nights" });
  assert.equal((await runtime(themes, rt)).status.packs.find((p) => p.id === "neon").name, "Neon Nights", "the name survives restarts");
  const reset = await runtime(themes, rt, ["--reset-name", "neon"]);
  const back = reset.status.packs.find((p) => p.id === "neon");
  assert.deepEqual([back.name, back.default_name], ["Neon", undefined]);
  assert.match((await runtime(themes, rt, ["--reset-name", "none"])).status.error, /not a pack that can be changed/);
});

// WCAG contrast between two #rgb or #rrggbb colors.
function contrast(a, b) {
  const lum = (hex) => {
    const h = hex.length === 4 ? [...hex.slice(1)].map((c) => c + c).join("") : hex.slice(1, 7);
    const [r, g, bl] = [0, 2, 4].map((i) => {
      const c = parseInt(h.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * bl;
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

test("every built-in wordmark has a color that reads on its dark and its light page", async () => {
  const { findPacks, openPackFiles } = await import("../lib/packfiles.mjs");
  const { loadPack } = await import("../lib/pack.mjs");
  const stock = Object.fromEntries(
    JSON.parse(readFileSync(join(here, "../catalog/tokens.json"), "utf8")).tokens.map((t) => [t.name, t.defaults]),
  );
  for (const found of findPacks(join(here, "../packs"))) {
    const { files, pack } = loadPack(openPackFiles(found));
    const wordmark = pack.assets?.["/assets/logotipo.svg"];
    if (!wordmark) continue;
    const colors = [...files.read(wordmark).toString("utf8").matchAll(/(?:fill|stroke|stop-color)="(#[0-9a-f]{3}(?:[0-9a-f]{3})?)"/gi)].map((m) => m[1]);
    for (const mode of ["dark", "light"]) {
      const page = pack.tokens?.[mode]?.["--r-color-bg"] ?? pack.tokens?.common?.["--r-color-bg"] ?? stock["--r-color-bg"][mode];
      const best = Math.max(...colors.map((c) => contrast(c, page)));
      assert.ok(best >= 3, `${pack.id}: the wordmark's best color is ${best.toFixed(1)}:1 on the ${mode} page ${page}; logos need 3:1`);
    }
  }
});

test("built-in packs keep their brand color readable under white button text", async () => {
  const { findPacks } = await import("../lib/packfiles.mjs");
  for (const found of findPacks(join(here, "../packs"))) {
    const pack = JSON.parse(readFileSync(join(found.path, "theme.json"), "utf8"));
    for (const scope of ["common", "dark", "light"]) {
      const brand = pack.tokens?.[scope]?.["--r-color-brand-primary"];
      if (!brand?.startsWith("#")) continue;
      assert.ok(contrast(brand, "#ffffff") >= 3, `${pack.id}: white on ${scope} brand ${brand} is ${contrast(brand, "#ffffff").toFixed(1)}:1; buttons need 3:1`);
    }
  }
});

test("accessibility packs keep every text color at 7:1 on their page", async () => {
  const { findPacks } = await import("../lib/packfiles.mjs");
  const TEXT = ["fg", "fg-heading", "fg-secondary", "fg-muted", "fg-faint", "danger-fg", "warning-fg", "success", "danger", "warning", "info"];
  const packs = findPacks(join(here, "../packs"))
    .map((found) => JSON.parse(readFileSync(join(found.path, "theme.json"), "utf8")))
    .filter((pack) => pack.tags?.includes("accessibility"));
  assert.ok(packs.length >= 3, "the accessibility packs are found");
  for (const pack of packs) {
    for (const mode of ["dark", "light"]) {
      const t = { ...pack.tokens.common, ...pack.tokens[mode] };
      for (const role of TEXT) {
        const color = t[`--r-color-${role}`];
        assert.ok(color, `${pack.id}: ${mode} sets --r-color-${role}`);
        const ratio = contrast(color, t["--r-color-bg"]);
        assert.ok(ratio >= 7, `${pack.id}: ${mode} --r-color-${role} ${color} is ${ratio.toFixed(1)}:1 on ${t["--r-color-bg"]}`);
      }
      assert.ok(contrast(t["--r-color-focus"], t["--r-color-bg"]) >= 3, `${pack.id}: ${mode} focus ring needs 3:1`);
    }
  }
});

test("pack tags are validated, and the schema agrees with the validator", async () => {
  const { PACK_TAGS_MAX } = await import("../lib/pack.mjs");
  const check = (tags) => validatePack({ files: folderFiles(tmpdir()), pack: { id: "t", name: "T", tags } }).errors.join();
  assert.equal(check(["accessibility", "retro"]), "");
  for (const bad of ["accessibility", ["Bad Tag"], Array(PACK_TAGS_MAX + 1).fill(0).map((_, i) => `t${i}`), ["a", "a"]]) {
    assert.match(check(bad), /tags/, JSON.stringify(bad));
  }
  const schema = JSON.parse(readFileSync(join(here, "../schema/theme.schema.json"), "utf8"));
  assert.equal(schema.properties.tags.maxItems, PACK_TAGS_MAX);
});

test("packs are listed accessibility first, then built-ins, then the themes folder", async () => {
  const folder = mkdtempSync(join(tmpdir(), "themeable-order-"));
  zipBuiltIn("aurora", folder, { extra: {} });
  const { renameSync } = await import("node:fs");
  renameSync(join(folder, "aurora.zip"), join(folder, "aaa.zip"));
  const { collectPacks, compileAll } = await import("../lib/compile.mjs");
  const result = compileAll({
    entries: collectPacks([{ dir: join(here, "../packs"), source: "built-in" }, { dir: folder, source: "folder" }]),
    catalog: { aliases: {} },
    outDir: mkdtempSync(join(tmpdir(), "themeable-out-")),
    loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
    pickerFile: join(here, "../picker/index.html"),
  });
  const order = result.packs.map((p) => p.id);
  assert.deepEqual(order.slice(0, 3), ["contrast-dark", "contrast-light", "signal"]);
  assert.equal(order.at(-1), "aaa", "a themes-folder pack comes after every built-in, whatever its name");
  assert.deepEqual(result.compiled.map((c) => c.meta.id), order.filter((id) => id !== "aaa"), "the manifest follows the same order");
});

test("Random draws only from the groups Branding includes", async () => {
  const { collectPacks, compileAll, RANDOM_POOL_DEFAULTS } = await import("../lib/compile.mjs");
  const run = (randomPool) =>
    compileAll({
      entries: collectPacks([{ dir: join(here, "../packs"), source: "built-in" }]),
      catalog: { aliases: {} },
      outDir: mkdtempSync(join(tmpdir(), "themeable-out-")),
      selected: "random",
      randomPool,
      loaderSource: readFileSync(join(here, "../loader/loader.js"), "utf8"),
      pickerFile: join(here, "../picker/index.html"),
    });
  const all = run(RANDOM_POOL_DEFAULTS).random.ids;
  assert.ok(all.includes("neon") && all.includes("signal") && !all.includes("none"));
  assert.deepEqual(run({ stock: true, built_in: false, accessibility: true }).random.ids, ["none", "contrast-dark", "contrast-light", "signal"]);
  assert.ok(!run({ accessibility: false }).random.ids.includes("signal"));
  const none = run({ stock: false, built_in: false, accessibility: false });
  assert.deepEqual(none.random.ids, []);
  assert.equal(none.effective, "none");
  assert.match(none.reason, /nothing to draw from/);
});

test("pack covers are validated and reach RomM's cover generator as CSS variables", async () => {
  const { COVER_VARS } = await import("../lib/client.mjs");
  const p = tempPack(
    { covers: { colors: { base: "#112233", icon: "#fff" }, missing: ["c/a.svg", "c/b.png"], unmatched: ["c/q.svg"] } },
    { "c/a.svg": "<svg/>", "c/b.png": "png", "c/q.svg": "<svg/>" },
  );
  assert.deepEqual(validatePack(p).errors, []);
  const { css, files, meta } = compilePack(p);
  assert.match(css, new RegExp(`${COVER_VARS.base}: #112233;`));
  assert.match(css, new RegExp(`${COVER_VARS.missing}: /themes/test/covers/missing-1\\.svg\\?v=\\w+ /themes/test/covers/missing-2\\.png\\?v=\\w+;`));
  assert.ok(files.some((f) => f.to === "themes/test/covers/unmatched-1.svg"));
  assert.match(meta.cover.url, /^\/themes\/test\/covers\/missing-1\.svg\?v=/);
  assert.deepEqual(meta.cover.colors, { base: "#112233", icon: "#fff" });

  const bad = (covers, files = {}) => validatePack(tempPack({ covers }, files)).errors.join(" | ");
  assert.match(bad({ colors: { base: "red" } }), /covers.colors.base: must be a #rgb/);
  assert.match(bad({ colors: { glow: "#fff" } }), /covers.colors.glow: use base/);
  assert.match(bad({ missing: [] }), /covers.missing: a list of 1 to 8/);
  assert.match(bad({ missing: ["../x.svg"] }), /covers.missing\[0\]: missing file inside the pack/);
  assert.match(bad({ missing: ["c.gif"] }, { "c.gif": "x" }), /use \.svg, \.png/);
  assert.match(bad({ extra: [] }), /covers.extra: use colors/);
});

test("every built-in pack ships placeholder cover art", async () => {
  const { findPacks } = await import("../lib/packfiles.mjs");
  for (const found of findPacks(join(here, "../packs"))) {
    const pack = JSON.parse(readFileSync(join(found.path, "theme.json"), "utf8"));
    assert.ok(pack.covers?.missing?.length && pack.covers?.unmatched?.length && pack.covers?.colors, `${pack.id} has covers`);
  }
});
