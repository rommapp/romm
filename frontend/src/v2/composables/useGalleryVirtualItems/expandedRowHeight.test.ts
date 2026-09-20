import { describe, expect, it } from "vitest";
import { computed, ref } from "vue";
import {
  LIST_ROW_DETAIL_HEIGHT_PX,
  LIST_ROW_HEIGHT_PX,
} from "@/v2/components/Gallery/listColumns";
import { useGalleryVirtualItems, type GalleryItem } from "./index";

/** Row heights for a three-row list, with row 1's panel settling at `open`. */
function rowHeights(open: number): number[] {
  const { virtualItems, getItemHeight } = useGalleryVirtualItems({
    layout: ref("list"),
    groupBy: ref("none"),
    total: ref(3),
    charIndex: ref({ a: 0 }),
    columns: ref(1),
    loadingInitial: computed(() => false),
    emptyMessage: ref(""),
    listSettledDetail: (position: number) => (position === 1 ? open : 0),
  });
  return virtualItems.value
    .filter(
      (i): i is Extract<GalleryItem, { kind: "list-row" }> =>
        i.kind === "list-row",
    )
    .map((row) => getItemHeight(row));
}

describe("useGalleryVirtualItems: list row with a detail panel", () => {
  it("keeps every row at the base height while none is open", () => {
    expect(rowHeights(0)).toEqual([
      LIST_ROW_HEIGHT_PX,
      LIST_ROW_HEIGHT_PX,
      LIST_ROW_HEIGHT_PX,
    ]);
  });

  it("grows the open row with its panel", () => {
    expect(rowHeights(LIST_ROW_DETAIL_HEIGHT_PX)).toEqual([
      LIST_ROW_HEIGHT_PX,
      LIST_ROW_HEIGHT_PX + LIST_ROW_DETAIL_HEIGHT_PX,
      LIST_ROW_HEIGHT_PX,
    ]);
  });
});
