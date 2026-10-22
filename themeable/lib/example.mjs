// Builds docs/theme.example.json: a pack with every option set, every token at its stock
// value and every replaceable file mapped, so authors can copy the parts they need.
import { EXCLUDED_ASSET_DIRS, ROOT_FILES } from "./pack.mjs";
import { SCOPES } from "./tokens.mjs";

/** Reads the Vuetify palettes of upstream's frontend/src/styles/themes.ts as { dark, light }. */
export function parseVuetifyThemes(source) {
  const objects = new Map();
  for (const m of source.matchAll(/const (\w+) = \{([\s\S]*?)\n\};/g)) objects.set(m[1], m[2]);
  const colorsOf = (body) => {
    const colors = {};
    for (const m of body.matchAll(/(?:"([a-z0-9-]+)"|([a-z][a-z0-9]*)):\s*"(#[0-9a-fA-F]{3,6})"|\.\.\.(\w+)/g)) {
      if (m[4]) Object.assign(colors, colorsOf(objects.get(m[4]) ?? ""));
      else colors[m[1] ?? m[2]] = m[3].toLowerCase();
    }
    return colors;
  };
  const palettes = {};
  for (const mode of ["dark", "light"]) {
    const body = objects.get(mode);
    if (!body) throw new Error(`themes.ts has no "${mode}" theme`);
    palettes[mode] = colorsOf(body);
    if (!Object.keys(palettes[mode]).length) throw new Error(`themes.ts "${mode}" theme has no colors`);
  }
  return palettes;
}

/** Reads RomM's placeholder cover palette (colorCoverArt) from upstream's frontend/src/v2/tokens/index.ts. */
export function parseCoverArt(source) {
  const body = source.match(/export const colorCoverArt = \{([\s\S]*?)\}/)?.[1];
  if (!body) throw new Error("tokens/index.ts has no colorCoverArt");
  return Object.fromEntries([...body.matchAll(/(\w+):\s*"(#[0-9a-fA-F]{3,6})"/g)].map((m) => [m[1], m[2].toLowerCase()]));
}

/** Reads the stock <meta name="theme-color"> from upstream's frontend/index.html. */
export function parseThemeColor(html) {
  const m = html.match(/<meta\s+name="theme-color"\s+content="(#[0-9a-fA-F]{3,6})"/);
  if (!m) throw new Error('index.html has no <meta name="theme-color">');
  return m[1].toLowerCase();
}

export function buildExample({ tokenCatalog, assetCatalog, vuetify, themeColor, coverArt }) {
  const tokens = {};
  for (const scope of SCOPES) {
    const entries = tokenCatalog.tokens.filter((t) => scope in t.defaults).map((t) => [t.name, t.defaults[scope]]);
    if (entries.length) tokens[scope] = Object.fromEntries(entries);
  }
  const assets = Object.fromEntries(
    [...assetCatalog.files]
      .filter((key) => !EXCLUDED_ASSET_DIRS.includes(key.split("/")[2]))
      .sort()
      .map((key) => [key, key.slice(1)]),
  );
  const rootFiles = Object.fromEntries([...ROOT_FILES].map((key) => [key, `root${key}`]));
  return {
    $schema: "../schema/theme.schema.json",
    id: "example",
    name: "Example",
    version: "1.0.0",
    author: "romm-themeable",
    description: "Every option, with each token at its stock value and each replaceable file listed",
    tags: ["example"],
    tokens,
    vuetify,
    assets,
    rootFiles,
    fonts: [{ family: "Example Sans", src: "fonts/ExampleSans-Variable.woff2", weight: "100 900", style: "normal", display: "swap" }],
    pwa: { themeColor },
    covers: { colors: coverArt, missing: ["covers/missing.svg"], unmatched: ["covers/unmatched.svg"] },
    extraCss: "custom.css",
  };
}
