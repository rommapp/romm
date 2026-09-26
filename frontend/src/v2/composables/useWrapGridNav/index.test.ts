import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import { useWrapGridNav } from "./index";

vi.mock("vue-router", () => ({
  useRoute: () => ({ fullPath: "/platforms" }),
}));

const TILE = 100;

// Two rows of two tiles, laid out by the data attributes since jsdom has no
// layout engine.
const Grid = defineComponent({
  setup() {
    const root = ref<HTMLElement | null>(null);
    useWrapGridNav(root, { cellSelector: ".cell" });
    return () =>
      h(
        "div",
        { ref: root },
        [0, 1].flatMap((row) =>
          [0, 1].map((col) =>
            h("button", {
              class: "cell",
              "data-row": row,
              "data-col": col,
            }),
          ),
        ),
      );
  },
});

describe("useWrapGridNav", () => {
  const { setModality } = useInputModality();
  const scrollIntoView = vi.fn();
  let wrapper: ReturnType<typeof mount> | null = null;
  const restores: (() => void)[] = [];

  function stub<K extends keyof HTMLElement>(
    key: K,
    descriptor: PropertyDescriptor,
  ) {
    const original = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      key,
    );
    Object.defineProperty(HTMLElement.prototype, key, {
      configurable: true,
      ...descriptor,
    });
    restores.push(() => {
      if (original) Object.defineProperty(HTMLElement.prototype, key, original);
      else delete (HTMLElement.prototype as Partial<HTMLElement>)[key];
    });
  }

  function cell(row: number, col: number): HTMLElement {
    return wrapper!.find(`[data-row="${row}"][data-col="${col}"]`)
      .element as HTMLElement;
  }

  function press(key: string) {
    document.activeElement!.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }),
    );
  }

  beforeEach(() => {
    setActivePinia(createPinia());
    setModality("mouse");
    scrollIntoView.mockClear();
    stub("offsetParent", {
      get(this: HTMLElement) {
        return this.parentElement;
      },
    });
    stub("getBoundingClientRect", {
      value(this: HTMLElement) {
        const top = Number(this.dataset.row ?? 0) * TILE;
        const left = Number(this.dataset.col ?? 0) * TILE;
        return new DOMRect(left, top, TILE, TILE);
      },
    });
    stub("scrollIntoView", { value: scrollIntoView });
    wrapper = mount(Grid, { attachTo: document.body });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    restores.splice(0).forEach((restore) => restore());
  });

  it("centres the row it moves to, so it clears the pinned top chrome", () => {
    cell(1, 0).focus();

    press("ArrowUp");

    expect(document.activeElement).toBe(cell(0, 0));
    expect(scrollIntoView).toHaveBeenLastCalledWith(
      expect.objectContaining({ block: "center" }),
    );

    press("ArrowDown");

    expect(document.activeElement).toBe(cell(1, 0));
    expect(scrollIntoView).toHaveBeenLastCalledWith(
      expect.objectContaining({ block: "center" }),
    );
  });

  it("keeps the page still when moving along a row", () => {
    cell(0, 0).focus();

    press("ArrowRight");

    expect(document.activeElement).toBe(cell(0, 1));
    expect(scrollIntoView).toHaveBeenLastCalledWith(
      expect.objectContaining({ block: "nearest" }),
    );
  });
});
