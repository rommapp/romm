import { describe, expect, it } from "vitest";
import {
  getListColumns,
  getSortOptions,
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

describe("grid-mode sort options", () => {
  it("offers exactly the axes the list headers make clickable", () => {
    expect(getSortOptions(true).map((option) => option.key)).toEqual([
      "name",
      "platform_id",
      "fs_size_bytes",
      "created_at",
      "first_release_date",
      "average_rating",
      "hltb_main_story",
    ]);
  });

  it("labels each axis with its column header", () => {
    const labels = new Map(
      getListColumns(true)
        .filter(isSortableColumn)
        .map((column) => [column.key, column.label]),
    );
    for (const option of getSortOptions(true)) {
      expect(option.label).toBe(labels.get(option.key));
    }
  });

  it("drops the platform axis on single-platform surfaces", () => {
    const keys = getSortOptions(false).map((option) => option.key);
    expect(keys).not.toContain("platform_id");
    expect(keys).toContain("name");
  });
});
