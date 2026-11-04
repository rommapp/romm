import { describe, expect, it } from "vitest";
import { computed, ref } from "vue";
import { useGalleryVirtualItems } from "./index";

// The backend only indexes letters for a lexically ordered result, so sorting
// the grid by size / rating / a date ships an empty `char_index`.
function build(charIndex: Record<string, number>) {
  const { virtualItems } = useGalleryVirtualItems({
    layout: ref("grid" as const),
    groupBy: ref("letter" as const),
    total: ref(5),
    charIndex: ref(charIndex),
    columns: ref(3),
    loadingInitial: computed(() => false),
    emptyMessage: ref("empty"),
    rowWidth: 600,
  });
  return virtualItems.value;
}

describe("grid grouping without a char index", () => {
  it("groups under letter headers when the server indexed them", () => {
    const items = build({ a: 0, b: 3 });

    expect(items.filter((it) => it.kind === "letter-header")).toHaveLength(2);
    expect(items.some((it) => it.kind === "row")).toBe(true);
  });

  it("falls back to flat rows instead of rendering nothing", () => {
    const items = build({});

    expect(items.filter((it) => it.kind === "row").length).toBeGreaterThan(0);
    expect(items.filter((it) => it.kind === "letter-header")).toHaveLength(0);
  });
});
