import api from "@/services/api";

// Shapes of /api/themeable/branding (backend/endpoints/themeable.py). The router
// is added by romm-themeable's overlay, so these are not in the generated types.

export interface ThemePack {
  id: string;
  name: string;
  description: string;
  author: string;
  version: string;
  source: "built-in" | "folder";
  swatch: string[];
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ThemeFolder {
  path: string;
  exists: boolean;
  writable: boolean;
  mounted: boolean;
}

export interface BrandingStatus {
  ok: boolean;
  generated: string;
  selected: string;
  effective: string;
  notes: string[];
  error: string | null;
  folder: ThemeFolder | null;
  packs: ThemePack[];
}

/** Pack id meaning "no theme": RomM's own look. */
export const STOCK_THEME = "none";

async function getBranding() {
  return api.get<BrandingStatus>("/themeable/branding");
}

async function rescanBranding() {
  return api.post<BrandingStatus>("/themeable/branding/rescan", {});
}

async function saveBranding(theme: string) {
  return api.put<BrandingStatus>("/themeable/branding", { theme });
}

export default { getBranding, rescanBranding, saveBranding };
