// useGalleryCoverRatios — the gallery's measured natural cover ratios.
//
// Covers render at their image's natural aspect, so the flow-packer needs
// each card's ratio (width = cardHeight * ratio) to decide where rows break.
// The API doesn't ship cover dimensions, so the only source is the image
// itself: GameCard reports `@ratio` once its cover loads, and this collects
// the values for the packer to read via `ratioAt(position)`.
//
// Keyed by rom id (not position), so the key survives a gallery context
// switch — a re-visited platform re-packs without re-waiting on images.
// Intentionally unbounded: two numbers per rom, reset on page reload.
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

export function useGalleryCoverRatios() {
  const galleryRoms = storeGalleryRoms();
  const ratioByRomId = new Map<number, number>();
  const ratioVersion = ref(0);
  let bumpTimer: ReturnType<typeof setTimeout> | null = null;

  /** Record a cover's measured ratio (GameCard's `@ratio` handler). */
  function onCardRatio(payload: { romId: number; ratio: number }) {
    const prev = ratioByRomId.get(payload.romId);
    if (prev != null && Math.abs(prev - payload.ratio) < RATIO_EPSILON) return;
    ratioByRomId.set(payload.romId, payload.ratio);
    if (bumpTimer) return;
    bumpTimer = setTimeout(() => {
      bumpTimer = null;
      ratioVersion.value++;
    }, REPACK_DEBOUNCE_MS);
  }

  /** Measured ratio for a position, or 0 when unknown (the packer then
   *  falls back to its default ratio). */
  function ratioAt(position: number): number {
    const romId = galleryRoms.romIdIndex[position];
    if (romId == null) return 0;
    return ratioByRomId.get(romId) ?? 0;
  }

  onBeforeUnmount(() => {
    if (bumpTimer) clearTimeout(bumpTimer);
  });

  return { ratioVersion, ratioAt, onCardRatio };
}
