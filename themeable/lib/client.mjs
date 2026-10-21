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
// Stock URLs the Branding tab shows per pack; nginx serves the pack's file for ?<cookie>=<id>.
export const PREVIEW_SLOTS = {
  background: "/assets/auth_background_static.svg",
  logo: "/assets/isotipo.svg",
  wordmark: "/assets/logotipo.svg",
  favicon: "/favicon-32x32.png",
};
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
  storage_key: STORAGE_KEY,
  cookie: COOKIE,
  url_param: URL_PARAM,
  preview_param: PREVIEW_PARAM,
  theme_attribute: THEME_ATTRIBUTE,
  stock_swatch: Object.values(STOCK_SWATCH),
  preview: { ...PREVIEW_SLOTS },
});
