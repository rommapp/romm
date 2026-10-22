// Values shared by the loader, picker and Branding tab; the compiler publishes them as the
// manifest's `client` section so the browser files never declare their own copies.
export const STOCK_ID = "none";
export const FOLLOW_SERVER_ID = "default";
// Resolved by the loader to a usable pack on every page load; never a pack's own id.
export const RANDOM_ID = "random";
export const STORAGE_KEY = "romm-themeable.theme";
export const COOKIE = "romm_theme";
export const URL_PARAM = "romm-theme";
export const PREVIEW_PARAM = "romm-theme-preview";
export const THEME_ATTRIBUTE = "data-romm-theme";
// The <link> the loader adds for a theme's stylesheet.
export const STYLESHEET_ID = "themeable-css";
// Stock URLs the Branding tab shows per pack; nginx serves the pack's file for ?<cookie>=<id>.
export const PREVIEW_SLOTS = {
  background: "/assets/auth_background_static.svg",
  logo: "/assets/isotipo.svg",
  wordmark: "/assets/logotipo.svg",
  favicon: "/favicon-32x32.png",
};
// The pack authoring guide, linked from Branding.
export const GUIDE_URL = "https://github.com/Stealthx3/romm-themeable/blob/main/themeable/docs/creating-a-theme-pack.md";
// The longest display name a pack can have; Rename checks it in the browser too.
export const PACK_NAME_MAX = 80;
// The pack tag that earns the Accessibility label and its own group in Random's draw.
export const ACCESSIBILITY_TAG = "accessibility";
// CSS variables a compiled theme sets for RomM's placeholder covers; patches/30-frontend-cover-art.mjs
// writes the same names into RomM's cover generator.
export const COVER_VARS = Object.freeze({
  base: "--themeable-cover-base",
  shade: "--themeable-cover-shade",
  warm: "--themeable-cover-warm",
  icon: "--themeable-cover-icon",
  missing: "--themeable-cover-missing",
  unmatched: "--themeable-cover-unmatched",
});
// How long the Branding preview for Random shows each pack.
export const RANDOM_CYCLE_MS = 2000;
export const STOCK_SWATCH = {
  "--r-color-bg": "#07070f",
  "--r-color-brand-primary": "#8b74e8",
  "--r-color-brand-accent": "#e1a38d",
};

export const CLIENT = Object.freeze({
  stock_id: STOCK_ID,
  follow_server_id: FOLLOW_SERVER_ID,
  random_id: RANDOM_ID,
  random_cycle_ms: RANDOM_CYCLE_MS,
  pack_name_max: PACK_NAME_MAX,
  guide_url: GUIDE_URL,
  accessibility_tag: ACCESSIBILITY_TAG,
  storage_key: STORAGE_KEY,
  cookie: COOKIE,
  url_param: URL_PARAM,
  preview_param: PREVIEW_PARAM,
  theme_attribute: THEME_ATTRIBUTE,
  stylesheet_id: STYLESHEET_ID,
  stock_swatch: Object.values(STOCK_SWATCH),
  preview: { ...PREVIEW_SLOTS },
});
