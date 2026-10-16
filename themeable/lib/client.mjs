// Values shared by the loader, picker and Branding tab; the compiler publishes them as the
// manifest's `client` section so the browser files never declare their own copies.
export const STOCK_ID = "none";
export const FOLLOW_SERVER_ID = "default";
export const STORAGE_KEY = "romm-themeable.theme";
export const COOKIE = "romm_theme";
export const URL_PARAM = "romm-theme";
export const PREVIEW_PARAM = "romm-theme-preview";
export const THEME_ATTRIBUTE = "data-romm-theme";
export const STOCK_SWATCH = {
  "--r-color-bg": "#07070f",
  "--r-color-brand-primary": "#8b74e8",
  "--r-color-brand-accent": "#e1a38d",
};

export const CLIENT = Object.freeze({
  stock_id: STOCK_ID,
  follow_server_id: FOLLOW_SERVER_ID,
  storage_key: STORAGE_KEY,
  cookie: COOKIE,
  url_param: URL_PARAM,
  preview_param: PREVIEW_PARAM,
  theme_attribute: THEME_ATTRIBUTE,
  stock_swatch: Object.values(STOCK_SWATCH),
});
