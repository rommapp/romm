// useGalleryCoverRatios — the gallery's measured natural cover ratios.
//
// Covers render at their image's natural aspect, so the flow-packer needs
// each card's ratio (width = cardHeight * ratio) to decide where rows break.
// The API doesn't ship cover dimensions, so the only source is the image
// itself: GameCard reports `@ratio` once its cover loads, and this collects
// the values for the packer to read via `ratioAt(position)`.
//
// The measurements live in a single module-level store (below), indexed by
// both rom id and image URL and shared with every GameCover — so a cover
// measured in the gallery is instantly known by id (the packer) or URL (the
// detail / player cover, for the shared-element morph). The packer keys by
// rom id, which survives a context switch — a re-visited platform re-packs
// without re-waiting on images.
//
// Updates batch behind `ratioVersion`: a burst of image loads bumps it once
// (after a short debounce) so the packed layout recomputes a single time
// instead of once per cover.
import { onBeforeUnmount, ref } from "vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";

// Below this delta a new measurement isn't worth a re-pack (sub-pixel noise).
const RATIO_EPSILON = 0.01;
// Wait this long after the last new ratio before bumping `ratioVersion`.
const REPACK_DEBOUNCE_MS = 150;

// ── Measured natural cover ratios — one page-lifetime, shared store ──
// Module-level (shared across every GameCover + composable instance) and
// indexed by BOTH the rom id and the resolved image URL, so a cover measured
// on any surface is found by whichever key the caller has: the gallery
// packer keys by rom id (position → id), a detail / player cover by URL or
// rom id (before its image loads), the morph by rom id. This is also what
// lets the detail/player cover paint at the right ratio immediately instead
// of the default 2/3 — without it the shared-element morph stretches to 2/3
// and snaps back on load.
//
// Rom-id keys are namespaced (`rom:<id>`) so a numeric id and a string id
// collapse to one entry and never collide with a URL. Intentionally
// unbounded — a couple of numbers per cover, reset on page reload.
const ratioByKey = new Map<string, number>();

function romKey(id: number | string): string {
  return `rom:${id}`;
}

interface RatioKeys {
  romId?: number | string | null;
  url?: string | null;
}

/** Measured natural ratio (w / h) by rom id and/or image URL — whichever is
 *  known — or null if neither has been measured yet. */
export function getCoverRatio({ romId, url }: RatioKeys): number | null {
  if (url) {
    const r = ratioByKey.get(url);
    if (r != null) return r;
  }
  if (romId != null) {
    const r = ratioByKey.get(romKey(romId));
    if (r != null) return r;
  }
  return null;
}

/** Remember a cover's measured ratio under its rom id and/or URL. */
export function setCoverRatio({ romId, url }: RatioKeys, ratio: number): void {
  if (url) ratioByKey.set(url, ratio);
  if (romId != null) ratioByKey.set(romKey(romId), ratio);
}

export function useGalleryCoverRatios() {
  const galleryRoms = storeGalleryRoms();
  const ratioVersion = ref(0);
  const maxRatio = ref(0);
  let bumpTimer: ReturnType<typeof setTimeout> | null = null;

  /** Record a cover's measured ratio (GameCard's `@ratio` handler). */
  function onCardRatio(payload: { romId: number; ratio: number }) {
    // Track the max on every report (even cached re-paints with an
    // unchanged ratio) so it rebuilds correctly after a context reset.
    if (payload.ratio > maxRatio.value) maxRatio.value = payload.ratio;
    const prev = getCoverRatio({ romId: payload.romId });
    if (prev != null && Math.abs(prev - payload.ratio) < RATIO_EPSILON) return;
    setCoverRatio({ romId: payload.romId }, payload.ratio);
    if (bumpTimer) return;
    bumpTimer = setTimeout(() => {
      bumpTimer = null;
      ratioVersion.value++;
    }, REPACK_DEBOUNCE_MS);
  }

  /** Reset the running max to the widest already-measured cover in the
   *  current gallery (or 0 if none) — call on a gallery context switch so
   *  a previous platform's wide covers don't keep the column wide. */
  function resetMaxRatio() {
    let m = 0;
    for (const romId of galleryRoms.romIdIndex) {
      const r = getCoverRatio({ romId });
      if (r != null && r > m) m = r;
    }
    maxRatio.value = m;
  }

  /** Measured ratio for a position, or 0 when unknown (the packer then
   *  falls back to its default ratio). */
  function ratioAt(position: number): number {
    const romId = galleryRoms.romIdIndex[position];
    if (romId == null) return 0;
    return getCoverRatio({ romId }) ?? 0;
  }

  onBeforeUnmount(() => {
    if (bumpTimer) clearTimeout(bumpTimer);
  });

  return { ratioVersion, ratioAt, onCardRatio, maxRatio, resetMaxRatio };
}
