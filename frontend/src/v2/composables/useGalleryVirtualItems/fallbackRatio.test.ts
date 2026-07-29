import { describe, expect, it } from "vitest";
import { computed, ref } from "vue";
import { useGalleryVirtualItems, type GalleryItem } from "./index";

// A 240px-tall card is 160px wide at box art (2/3) and 240px wide at square
// (miximage / physical). In an 800px row that is 4 per row vs 3 per row —
// pack a square-painted card as box art and the row overflows.
const CARD_HEIGHT = 240;
const ROW_WIDTH = 800;

function packedRows(fallbackRatio?: number): Array<[number, number]> {
  const { virtualItems } = useGalleryVirtualItems({
    layout: ref("grid"),
    groupBy: ref("none"),
    total: ref(6),
    charIndex: ref({ a: 0 }),
    columns: ref(6),
    loadingInitial: computed(() => false),
    emptyMessage: ref(""),
    cardHeight: CARD_HEIGHT,
    rowWidth: ROW_WIDTH,
    gap: 12,
    fallbackRatio,
  });
  return virtualItems.value
    .filter((i): i is Extract<GalleryItem, { kind: "row" }> => i.kind === "row")
    .map((r) => [r.startPosition, r.endPosition]);
}

describe("useGalleryVirtualItems — unmeasured cover ratio", () => {
  it("packs unmeasured positions as box art by default", () => {
    expect(packedRows()).toEqual([
      [0, 4],
      [4, 6],
    ]);
  });

  it("packs unmeasured positions at the active style's ratio", () => {
    // Square style (miximage / physical): a card with no artwork paints its
    // placeholder square and never measures, so it must reserve 240px.
    expect(packedRows(1)).toEqual([
      [0, 3],
      [3, 6],
    ]);
  });

  it("ignores a non-positive fallback ratio", () => {
    expect(packedRows(0)).toEqual([
      [0, 4],
      [4, 6],
    ]);
  });
});
