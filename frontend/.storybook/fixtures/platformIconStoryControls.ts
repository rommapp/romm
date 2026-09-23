import { DEFAULT_PLATFORM_ICON } from "../../src/v2/composables/usePlatformIconCache/iconCache";
import { STORYBOOK_NON_CACHED_ICON_SVG } from "./urls";

export const PLATFORM_ICON_SIZE_MAX = 128;
export const PLATFORM_ICON_SIZE_MIN = -1;

/** Literal `src` values passed through to components / `<img>`. */
export const SHIPPED_SNES_SRC = "/assets/platforms/snes.svg";
export const SHIPPED_NES_SRC = "/assets/platforms/nes.svg";
export const SHIPPED_GBA_SRC = "/assets/platforms/gba.svg";
export const MISSING_PROD_SRC = "/assets/platforms/does-not-exist.svg";

export const R_PLATFORM_ICON_SRC_OPTIONS = [
  SHIPPED_SNES_SRC,
  SHIPPED_NES_SRC,
  SHIPPED_GBA_SRC,
  MISSING_PROD_SRC,
  STORYBOOK_NON_CACHED_ICON_SVG,
] as const;

export const rPlatformIconSrcLabels: Record<
  (typeof R_PLATFORM_ICON_SRC_OPTIONS)[number],
  string
> = {
  [SHIPPED_SNES_SRC]: "SNES (shipped)",
  [SHIPPED_NES_SRC]: "NES (shipped)",
  [SHIPPED_GBA_SRC]: "GBA (shipped)",
  [MISSING_PROD_SRC]: "Missing prod (fallback)",
  [STORYBOOK_NON_CACHED_ICON_SVG]: "Storybook fixture",
};

export const rPlatformIconDefaultArgs = {
  src: SHIPPED_SNES_SRC,
  useFallback: true,
  fallbackSrc: DEFAULT_PLATFORM_ICON,
  size: 32,
  alt: "Super Nintendo",
  title: "Super Nintendo Entertainment System",
  showTooltip: true,
};

export const PLATFORM_ICON_SLUG_OPTIONS = [
  "snes",
  "nes",
  "gba",
  "switch_mods",
  "non-cached-icon",
] as const;

export const platformIconSlugLabels: Record<
  (typeof PLATFORM_ICON_SLUG_OPTIONS)[number],
  string
> = {
  snes: "snes (shipped)",
  nes: "nes (shipped)",
  gba: "gba (shipped)",
  switch_mods: "switch_mods (default)",
  "non-cached-icon": "non-cached-icon (default)",
};

export const PLATFORM_ICON_SRC_OPTIONS = [
  STORYBOOK_NON_CACHED_ICON_SVG,
  MISSING_PROD_SRC,
  SHIPPED_SNES_SRC,
] as const;

export const platformIconSrcLabels: Record<
  (typeof PLATFORM_ICON_SRC_OPTIONS)[number],
  string
> = {
  [STORYBOOK_NON_CACHED_ICON_SVG]: "Storybook fixture",
  [MISSING_PROD_SRC]: "Missing prod",
  [SHIPPED_SNES_SRC]: "snes.svg override",
};

export const platformIconDefaultArgs = {
  slug: "snes" as (typeof PLATFORM_ICON_SLUG_OPTIONS)[number],
  fsSlug: "",
  overrideSrc: false,
  src: STORYBOOK_NON_CACHED_ICON_SVG,
  size: 32,
  alt: "Super Nintendo",
  title: "Super Nintendo Entertainment System",
  showTooltip: true,
};

/** Props panel only lists story args (avoids extra Vue props with undefined). */
export const platformIconStoryControlInclude = [
  "slug",
  "fsSlug",
  "overrideSrc",
  "src",
  "size",
  "alt",
  "title",
  "showTooltip",
] as const;

export const rPlatformIconStoryControlInclude = [
  "src",
  "useFallback",
  "fallbackSrc",
  "size",
  "alt",
  "title",
  "showTooltip",
] as const;
