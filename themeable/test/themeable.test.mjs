import assert from "node:assert/strict";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
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
  assert.match(patched, /map "\$arg_romm_theme:\$cookie_romm_theme" \$themeable_theme \{\n {4}default "ember";/);
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
    const { errors } = validatePack({ dir: tmpdir(), pack: { id, name: id } });
    assert.ok(errors.some((e) => e.includes("reserved")), `validator reserves ${id}`);
  }
});

test("browser files read shared values from the manifest instead of declaring them", async () => {
  const { CLIENT } = await import("../lib/client.mjs");
  const files = [
    "loader/loader.js",
    "picker/index.html",
    "overlay/frontend/src/v2/components/Settings/BrandingSection.vue",
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
  const { buildExample, parseThemeColor, parseVuetifyThemes } = await import("../lib/example.mjs");
  const { loadCatalog } = await import("../lib/catalog.mjs");
  const { ROOT_FILES } = await import("../lib/pack.mjs");
  const frontend = join(here, "..", "..", "frontend");
  const readJson = (f) => JSON.parse(readFileSync(join(here, "..", f), "utf8"));
  const expected = buildExample({
    tokenCatalog: readJson("catalog/tokens.json"),
    assetCatalog: readJson("catalog/assets.json"),
    vuetify: parseVuetifyThemes(readFileSync(join(frontend, "src/styles/themes.ts"), "utf8")),
    themeColor: parseThemeColor(readFileSync(join(frontend, "index.html"), "utf8")),
  });
  const example = readJson("docs/theme.example.json");
  assert.deepEqual(example, expected, "run `npm run example`");

  const schema = readJson("schema/theme.schema.json");
  assert.deepEqual(Object.keys(example).sort(), Object.keys(schema.properties).sort(), "every top-level option is set");
  assert.deepEqual(Object.keys(example.rootFiles).sort(), [...ROOT_FILES].sort());
  const catalog = loadCatalog(join(here, "..", "catalog"));
  assert.equal(Object.keys(example.assets).length, catalog.assets.size, "every replaceable file is listed");
  assert.equal(new Set(Object.values(example.tokens).flatMap(Object.keys)).size, catalog.tokens.size, "every token is listed");
  const { errors } = validatePack({ dir: tmpdir(), pack: example }, catalog);
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
  assert.match(patched, new RegExp(`map \\$arg_${COOKIE} \\$themeable_root \\{`));
  assert.match(patched, /try_files \$themeable_root\$uri \$uri =404;/);
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
  const manifest = { default: RANDOM_ID, client: CLIENT, themes };
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

  const one = { ...manifest, themes: themes.slice(1, 2) };
  assert.equal(runLoader(one, { cookie: `${CLIENT.cookie}=ember` }).theme, "ember", "a single pack is drawn even if shown last");
  assert.equal(runLoader({ ...manifest, themes: [] }, { stored: RANDOM_ID }).theme, STOCK_ID, "nothing to draw from means RomM's look");
});

test("a browser can choose Random for itself, and a Random preview leaves the cookie alone", async () => {
  const { CLIENT, RANDOM_ID } = await import("../lib/client.mjs");
  const themes = ["aurora", "ember"].map((id) => ({ id, name: id, css: `/themes/${id}/theme.css` }));
  const manifest = { default: "ember", client: CLIENT, themes };
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
  assert.match(empty.reason, /no usable packs/);
});
