// useCoverArt — single source of truth for what image a game cover shows
// and at what aspect ratio.
//
// v1 spread this across three places: `stores/galleryView.getAspectRatio`
// (ratios), `Base.vue`'s `largeCover`/`smallCover` computeds (URL chain),
// and the deprecated `useGameAnimation` (alt-art resolution + motion
// flags). v2 folds all of it here so every surface that paints a rom's
// own cover (gallery grids, list rows, related games, home rows) stays
// consistent.
//
// The `boxartStyle` user preference (gallery-wide) picks WHICH artwork a
// card shows and therefore its canonical aspect ratio — the four ratios
// map to known artwork sources:
//   * cover_path    → 2/3   box art       (object-fit: cover)
//   * box3d_path    → 3/4   3D box render (object-fit: contain)
//   * physical_path → 1/1   disc/cartridge (contain; CD spins, cart drops)
//   * miximage_path → 1/1   mix image     (contain; hover video overlay)
//
// Alt-art paths come from `ss_metadata` (preferred) or `gamelist_metadata`
// and are relative to `FRONTEND_RESOURCES_PATH`. The local cover chain
// (`path_cover_large` → `path_cover_small`) gets a webp rewrite when the
// server serves webp; alt-art / explicit override URLs are treated as
// final.
//
//   const art = useCoverArt(() => props.rom);
//   <img :src="art.coverUrl.value" :style="{ objectFit: art.objectFit.value }" />
import {
  computed,
  toValue,
  type ComputedRef,
  type MaybeRefOrGetter,
} from "vue";
import { useUISettings } from "@/composables/useUISettings";
import type { SimpleRom } from "@/stores/roms";
import {
  FRONTEND_RESOURCES_PATH,
  isCDBasedSystem,
  isArcadeSystem,
} from "@/utils";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

export type BoxartStyle =
  "cover_path" | "box3d_path" | "physical_path" | "miximage_path";

/** Styles that resolve to an alternative artwork on the rom's metadata
 *  (everything except the default box art). These literals are exactly
 *  the path keys shared by `RomSSMetadata` and `RomGamelistMetadata`. */
export type AltBoxartStyle = Exclude<BoxartStyle, "cover_path">;

/** The cover-relevant slice of a rom — both `SimpleRom` (gallery) and
 *  `DetailedRom` (detail page) satisfy it, so cover resolution works the
 *  same on every surface without coupling to one schema. */
export type CoverArtRom = Pick<
  SimpleRom,
  | "ss_metadata"
  | "gamelist_metadata"
  | "path_cover_large"
  | "path_cover_small"
  | "url_cover"
  | "path_video"
  | "platform_slug"
>;

/** Canonical width/height ratio per style — mirrors v1's
 *  `galleryView.getAspectRatio`. The ratio is purely style-driven (a
 *  rom missing its alt art still letterboxes the fallback cover in the
 *  style's box, matching v1). */
export const COVER_RATIOS: Record<BoxartStyle, number> = {
  cover_path: 2 / 3,
  box3d_path: 3 / 4,
  physical_path: 1,
  miximage_path: 1,
};

const RASTER_EXT = /\.(png|jpe?g)$/i;

export function isBoxartStyle(value: unknown): value is BoxartStyle {
  return (
    value === "cover_path" ||
    value === "box3d_path" ||
    value === "physical_path" ||
    value === "miximage_path"
  );
}

export function coverRatio(style: BoxartStyle): number {
  return COVER_RATIOS[style];
}

/** Relative metadata path for an alt-art style, preferring ScreenScraper
 *  over the gamelist source. Returns null for `cover_path` (no alt art)
 *  or when neither provider has the asset. */
export function altArtPath(
  rom: CoverArtRom,
  style: BoxartStyle,
): string | null {
  if (style === "cover_path") return null;
  const key = style satisfies AltBoxartStyle;
  return rom.ss_metadata?.[key] ?? rom.gamelist_metadata?.[key] ?? null;
}

export interface CoverArtDescriptor {
  /** Primary image src — alt artwork, explicit override, or the local
   *  cover chain. Null when the rom has no usable image (→ placeholder). */
  coverUrl: string | null;
  /** Secondary src tried on `coverUrl` load error (external provider). */
  fallbackUrl: string | null;
  /** Any real image is available (so the card paints art, not a
   *  placeholder). */
  hasArtwork: boolean;
  /** True when the rendered image is a non-cover style artwork (drives
   *  `object-fit: contain` and enables motion). */
  isAltArt: boolean;
  /** width / height of the cover box for the active style. */
  ratio: number;
  /** `cover` fills the box (box art); `contain` shows the whole artwork
   *  un-cropped (3D box, disc, mix image). */
  objectFit: "cover" | "contain";
  /** Disc-spin animation applies (physical art on a CD-based platform). */
  animateCD: boolean;
  /** Cartridge drop-in animation applies (physical art, non-CD platform). */
  animateCartridge: boolean;
  /** Hover-video src for the miximage style, or null. */
  videoUrl: string | null;
}

interface ComputeOptions {
  resourcesPath: string;
  supportsWebp: boolean;
  /** Explicit cover URL that bypasses the resolution chain (preview
   *  blobs, external provider URLs). Treated as final — no webp rewrite,
   *  no alt-art swap. */
  coverSrc?: string | null;
}

/** Pure resolution core — no Vue, no stores. Exported for unit tests and
 *  for non-reactive call sites. */
export function computeCoverArt(
  rom: CoverArtRom,
  style: BoxartStyle,
  opts: ComputeOptions,
): CoverArtDescriptor {
  const ratio = coverRatio(style);
  // Treat an empty string as "no override" — a preview field that hasn't
  // been set yet (e.g. EditRomDialog opens `imagePreviewUrl = ""`) must
  // still resolve the rom's own cover, not blank out to the placeholder.
  const override =
    opts.coverSrc && opts.coverSrc.length > 0 ? opts.coverSrc : null;
  const altPath = altArtPath(rom, style);
  const isAltArt = !override && altPath != null;

  let coverUrl: string | null;
  if (override != null) {
    coverUrl = override;
  } else if (altPath != null) {
    coverUrl = `${opts.resourcesPath}/${altPath}`;
  } else {
    const local = rom.path_cover_large ?? rom.path_cover_small ?? null;
    coverUrl =
      local && opts.supportsWebp ? local.replace(RASTER_EXT, ".webp") : local;
  }

  const fallbackUrl = override != null ? null : (rom.url_cover ?? null);
  const hasArtwork = Boolean(coverUrl || fallbackUrl);

  const physicalAlt = style === "physical_path" && isAltArt;
  const cdBased = physicalAlt && isCDBasedSystem(rom.platform_slug);
  const arcadeBased = physicalAlt && isArcadeSystem(rom.platform_slug);

  const videoUrl =
    style === "miximage_path" && rom.path_video
      ? `${opts.resourcesPath}/${rom.path_video}`
      : null;

  return {
    coverUrl,
    fallbackUrl,
    hasArtwork,
    isAltArt,
    ratio,
    objectFit: style === "cover_path" ? "cover" : "contain",
    animateCD: physicalAlt && cdBased,
    animateCartridge: physicalAlt && !cdBased && !arcadeBased,
    videoUrl,
  };
}

export interface UseCoverArtOptions {
  /** Override the gallery-wide `boxartStyle` preference (stories,
   *  pickers that always show box art). */
  forceStyle?: MaybeRefOrGetter<BoxartStyle>;
  /** Explicit cover URL — see {@link ComputeOptions.coverSrc}. When set
   *  without an explicit `forceStyle`, the style resolves to `cover_path`
   *  so preview blobs / external provider URLs render as plain box art
   *  (2/3, object-fit cover) regardless of the gallery's active style. */
  coverSrc?: MaybeRefOrGetter<string | null | undefined>;
  /** Override webp support detection. `undefined` (default) falls back to
   *  `useWebpSupport`. Lets a parent that already resolved the flag pass
   *  it down instead of every card re-reading the heartbeat store. */
  webp?: MaybeRefOrGetter<boolean | undefined>;
}

export interface UseCoverArt {
  style: ComputedRef<BoxartStyle>;
  coverUrl: ComputedRef<string | null>;
  fallbackUrl: ComputedRef<string | null>;
  hasArtwork: ComputedRef<boolean>;
  isAltArt: ComputedRef<boolean>;
  ratio: ComputedRef<number>;
  objectFit: ComputedRef<"cover" | "contain">;
  animateCD: ComputedRef<boolean>;
  animateCartridge: ComputedRef<boolean>;
  videoUrl: ComputedRef<string | null>;
  /** False when the user disabled animations — the card multiplies this
   *  with `animateCD` / `animateCartridge` / video playback. */
  motionEnabled: ComputedRef<boolean>;
}

export function useCoverArt(
  rom: MaybeRefOrGetter<CoverArtRom | null | undefined>,
  options: UseCoverArtOptions = {},
): UseCoverArt {
  const { boxartStyle, disableAnimations } = useUISettings();
  const { supportsWebp } = useWebpSupport();

  const coverSrc = computed<string | undefined>(() => {
    const v = options.coverSrc ? toValue(options.coverSrc) : undefined;
    // Empty string = "no override" (an unset preview field) → resolve the
    // rom's own cover rather than forcing a blank box-art override.
    return v || undefined;
  });

  const style = computed<BoxartStyle>(() => {
    const forced = options.forceStyle ? toValue(options.forceStyle) : undefined;
    if (forced) return forced;
    // An explicit override URL is a plain cover (preview / provider art),
    // not an alt-art style — present it as box art.
    if (coverSrc.value != null) return "cover_path";
    return isBoxartStyle(boxartStyle.value) ? boxartStyle.value : "cover_path";
  });

  const effectiveWebp = computed<boolean>(() => {
    const override = options.webp ? toValue(options.webp) : undefined;
    return override === undefined ? supportsWebp.value : override;
  });

  const descriptor = computed<CoverArtDescriptor>(() => {
    const r = toValue(rom);
    const s = style.value;
    // No rom yet (e.g. detail / player view before the fetch resolves) —
    // surface a style-shaped empty descriptor so consumers still get the
    // right ratio / object-fit and any explicit override URL.
    if (!r) {
      const src = coverSrc.value ?? null;
      return {
        coverUrl: src,
        fallbackUrl: null,
        hasArtwork: !!src,
        isAltArt: false,
        ratio: coverRatio(s),
        objectFit: s === "cover_path" ? "cover" : "contain",
        animateCD: false,
        animateCartridge: false,
        videoUrl: null,
      };
    }
    return computeCoverArt(r, s, {
      resourcesPath: FRONTEND_RESOURCES_PATH,
      supportsWebp: effectiveWebp.value,
      coverSrc: coverSrc.value,
    });
  });

  return {
    style,
    coverUrl: computed(() => descriptor.value.coverUrl),
    fallbackUrl: computed(() => descriptor.value.fallbackUrl),
    hasArtwork: computed(() => descriptor.value.hasArtwork),
    isAltArt: computed(() => descriptor.value.isAltArt),
    ratio: computed(() => descriptor.value.ratio),
    objectFit: computed(() => descriptor.value.objectFit),
    animateCD: computed(() => descriptor.value.animateCD),
    animateCartridge: computed(() => descriptor.value.animateCartridge),
    videoUrl: computed(() => descriptor.value.videoUrl),
    motionEnabled: computed(() => !disableAnimations.value),
  };
}
