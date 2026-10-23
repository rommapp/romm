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
  /** How the pack is stored; packs in the themes folder are always archives. */
  format: "zip" | "folder";
  tags: string[];
  /** A renamed built-in pack's own name, for Reset name. */
  default_name?: string | null;
  /** The first missing-cover art, or the colors RomM's generated art uses; null for neither. */
  cover: PackCover | null;
  swatch: string[];
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface PackCover {
  url: string | null;
  colors: Partial<Record<"base" | "shade" | "warm" | "icon", string>> | null;
}

export interface ThemeFolder {
  path: string;
  exists: boolean;
  writable: boolean;
  mounted: boolean;
}

/** Values shared with the theme loader and picker; their one home is themeable/lib/client.mjs. */
export interface ThemeableClient {
  stock_id: string;
  follow_server_id: string;
  random_id: string;
  pack_id_pattern: string;
  random_cycle_ms: number;
  pack_name_max: number;
  /** The "Creating a theme pack" guide on GitHub. */
  guide_url: string;
  /** The tag that earns the Accessibility label and Random's accessibility group. */
  accessibility_tag: string;
  storage_key: string;
  cookie: string;
  url_param: string;
  preview_param: string;
  theme_attribute: string;
  stylesheet_id: string;
  stock_swatch: string[];
  /** Stock URL per preview slot; `?<cookie>=<id>` makes nginx serve that pack's file. */
  preview: Record<PreviewSlot, string>;
}

export type PreviewSlot = "background" | "logo" | "wordmark" | "favicon";

export interface BrandingStatus {
  ok: boolean;
  generated: string;
  selected: string;
  effective: string;
  notes: string[];
  error: string | null;
  client: ThemeableClient | null;
  folder: ThemeFolder | null;
  packs: ThemePack[];
  /** Built-in packs hidden by Delete; Restore built-in packs shows them again. */
  hidden: string[];
  /** Random's groups and the ids they leave it to draw from. */
  random: RandomPool | null;
  /** The largest pack upload the server accepts. */
  max_upload_bytes: number;
}

export interface RandomGroups {
  stock: boolean;
  built_in: boolean;
  accessibility: boolean;
}

export interface RandomPool extends RandomGroups {
  ids: string[];
  /** The ids each switch covers; `always` holds uploaded packs, which are always drawn. */
  members: Record<Exclude<keyof RandomGroups, "stock"> | "always", string[]>;
}

/** Why an upload was refused with 422. */
export interface PackProblems {
  message: string;
  problems: string[];
}

/** An upload whose id is already installed (409); send it again with `replace` to confirm. */
export interface PackClash {
  message: string;
  id: string;
  name: string;
}

/** Stock URL plus the theme argument: nginx answers with the pack's file, or RomM's own
 * where the pack doesn't replace it. */
export function artworkUrl(
  client: ThemeableClient,
  id: string,
  slot: PreviewSlot,
): string {
  if (!client.preview?.[slot]) return "";
  return `${client.preview[slot]}?${client.cookie}=${encodeURIComponent(id)}`;
}

async function getBranding() {
  return api.get<BrandingStatus>("/themeable/branding");
}

async function rescanBranding() {
  return api.post<BrandingStatus>("/themeable/branding/rescan", {});
}

async function saveBranding(theme: string, random?: RandomGroups) {
  return api.put<BrandingStatus>("/themeable/branding", { theme, random });
}

async function uploadPack(file: File, replace = false) {
  const form = new FormData();
  form.append("file", file);
  return api.post<BrandingStatus>("/themeable/packs", form, {
    params: replace ? { replace: true } : {},
  });
}

/** Renames a pack; `null` gives a renamed built-in pack its own name back. */
async function renamePack(id: string, name: string | null) {
  return api.patch<BrandingStatus>(
    `/themeable/packs/${encodeURIComponent(id)}`,
    { name },
  );
}

async function deletePack(id: string) {
  return api.delete<BrandingStatus>(
    `/themeable/packs/${encodeURIComponent(id)}`,
  );
}

async function restoreBuiltInPacks() {
  return api.post<BrandingStatus>("/themeable/packs/built-ins/restore", {});
}

export default {
  getBranding,
  rescanBranding,
  saveBranding,
  uploadPack,
  renamePack,
  deletePack,
  restoreBuiltInPacks,
};
