// useBoxFaces — resolves the three flat scans an interactive 3D box needs
// (front / back / spine) for a rom, and reports whether the full set is
// available.
//
//   * front  — the rom's own cover chain (the ScreenScraper box-2D front
//              becomes the cover on match), webp-rewritten like everywhere
//              else.
//   * back   — ss_metadata.box2d_back_path
//   * spine  — ss_metadata.box2d_side_path
//
// Back and spine are persisted locally only when the user enabled the
// `box2d_back` / `box2d_side` media types in `scan.media`, so `complete`
// is false for most libraries until they opt in and re-scan. RBox3D is
// only mounted when `complete` is true; otherwise the surface keeps the
// flat cover.
import { computed, toValue, type ComputedRef, type MaybeRefOrGetter } from "vue";
import type { SimpleRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";

/** The face-relevant slice of a rom — satisfied by both `SimpleRom` and
 *  `DetailedRom`. */
export type BoxFacesRom = Pick<
  SimpleRom,
  "ss_metadata" | "path_cover_large" | "path_cover_small"
>;

export interface BoxFaces {
  front: string | null;
  back: string | null;
  spine: string | null;
  /** All three faces resolved → the rom can render as a real 3D box. */
  complete: boolean;
}

const RASTER_EXT = /\.(png|jpe?g)$/i;

function resourceUrl(path: string | null | undefined): string | null {
  return path ? `${FRONTEND_RESOURCES_PATH}/${path}` : null;
}

/** Pure resolution core — no Vue, exported for unit tests. */
export function computeBoxFaces(
  rom: BoxFacesRom,
  supportsWebp: boolean,
): BoxFaces {
  const localCover = rom.path_cover_large ?? rom.path_cover_small ?? null;
  const front =
    localCover && supportsWebp
      ? localCover.replace(RASTER_EXT, ".webp")
      : localCover;

  const back = resourceUrl(rom.ss_metadata?.box2d_back_path);
  const spine = resourceUrl(rom.ss_metadata?.box2d_side_path);

  return {
    front,
    back,
    spine,
    complete: Boolean(front && back && spine),
  };
}

export function useBoxFaces(
  rom: MaybeRefOrGetter<BoxFacesRom | null | undefined>,
): ComputedRef<BoxFaces> {
  const { supportsWebp } = useWebpSupport();
  return computed(() => {
    const r = toValue(rom);
    if (!r) return { front: null, back: null, spine: null, complete: false };
    return computeBoxFaces(r, supportsWebp.value);
  });
}
