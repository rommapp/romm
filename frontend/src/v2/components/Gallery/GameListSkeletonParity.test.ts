import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GameListRow from "./GameListRow.vue";
import GameListSkeletonRow from "./GameListSkeletonRow.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en" } }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

/** Per-column placeholder geometry, read off each block's inline width/height. */
function shapes(row: HTMLElement): string[][] {
  return Array.from(row.children).map((cell) =>
    Array.from(cell.querySelectorAll<HTMLElement>(".r-skeleton")).map(
      (block) => `${block.style.width}x${block.style.height}`,
    ),
  );
}

describe("list-mode skeleton row", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("paints the bootstrap row's per-column shapes", () => {
    // Both placeholder rows sit in the same column grid, so a shape that drifts
    // between them reflows the list when data arrives.
    const pending = mount(GameListRow, { props: { position: 0 } }).element;
    const bootstrap = mount(GameListSkeletonRow).element;

    expect(shapes(pending)).toEqual(shapes(bootstrap));
  });
});
