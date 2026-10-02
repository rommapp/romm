import { describe, expect, it } from "vitest";
import { computed, ref } from "vue";
import type { LayoutMode } from "@/v2/composables/useGalleryMode";
import { useGalleryVirtualItems, type GalleryItem } from "./index";

function skeletons(layout: LayoutMode, skeletonTotal: number) {
  const { virtualItems } = useGalleryVirtualItems({
    layout: ref(layout),
    groupBy: ref("none"),
    total: ref(0),
    charIndex: ref({}),
    columns: ref(5),
    loadingInitial: computed(() => true),
    emptyMessage: ref(""),
    skeletonRowCount: 4,
    skeletonTotal: ref(skeletonTotal),
  });
  return virtualItems.value;
}

const cardsPerRow = (items: GalleryItem[]) =>
  items.map((i) => (i.kind === "skeleton-row" ? i.cards : -1));

describe("useGalleryVirtualItems skeleton count", () => {
  it("paints full grid rows when the count is unknown", () => {
    expect(cardsPerRow(skeletons("grid", 0))).toEqual([5, 5, 5, 5]);
  });

  it("paints only the known count in the grid", () => {
    expect(cardsPerRow(skeletons("grid", 3))).toEqual([3]);
    expect(cardsPerRow(skeletons("grid", 7))).toEqual([5, 2]);
  });

  it("never paints more than the default in the grid", () => {
    expect(cardsPerRow(skeletons("grid", 500))).toEqual([5, 5, 5, 5]);
  });

  it("paints only the known count in the list", () => {
    expect(skeletons("list", 0)).toHaveLength(16);
    expect(skeletons("list", 2)).toHaveLength(2);
    expect(skeletons("list", 500)).toHaveLength(16);
  });
});
