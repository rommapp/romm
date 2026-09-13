import { describe, expect, it } from "vitest";
import {
  getListColumns,
  isListSortKey,
  isSortableColumn,
} from "@/v2/components/Gallery/listColumns";

describe("list column sort keys", () => {
  it("recognises every sortable column as a sort key", () => {
    // A sortable column missing here is silently stuck ascending and
    // unhighlighted: the header reads both off `isListSortKey`.
    for (const column of getListColumns(true).filter(isSortableColumn)) {
      expect(isListSortKey(column.key)).toBe(true);
    }
  });

  it("recognises the platform column, which a hand-kept copy had dropped", () => {
    expect(isListSortKey("platform_id")).toBe(true);
  });

  it("rejects display-only columns and unknown keys", () => {
    expect(isListSortKey("cover")).toBe(false);
    expect(isListSortKey("actions")).toBe(false);
    expect(isListSortKey("last_played")).toBe(false);
  });
});
