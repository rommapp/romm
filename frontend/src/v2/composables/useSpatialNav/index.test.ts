import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import storePlaying from "@/stores/playing";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSpatialNav } from "./index";

vi.mock("vue-router", () => ({
  useRoute: () => ({ fullPath: "/rom/1" }),
}));

// Laid out by data attributes since jsdom has no layout engine: a top bar
// link, the game page's action ribbon (a single-row useGridNav) under it,
// and a tab below the ribbon.
const Page = defineComponent({
  setup() {
    const ribbon = ref<HTMLElement | null>(null);
    useGridNav(ribbon, {
      getRows: () => (ribbon.value ? [ribbon.value] : []),
    });
    useSpatialNav().install();
    const btn = (id: string, x: number, y: number) =>
      h("button", { id, "data-x": x, "data-y": y });
    return () =>
      h("div", [
        btn("nav", 0, 0),
        h("div", { ref: ribbon }, [btn("play", 0, 300), btn("fav", 100, 300)]),
        btn("tab", 0, 500),
      ]);
  },
});

describe("useSpatialNav", () => {
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

  function el(id: string): HTMLElement {
    return document.getElementById(id)!;
  }

  function press(key: string): KeyboardEvent {
    const event = new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
    });
    document.activeElement!.dispatchEvent(event);
    return event;
  }

  beforeEach(() => {
    setActivePinia(createPinia());
    scrollIntoView.mockClear();
    stub("getBoundingClientRect", {
      value(this: HTMLElement) {
        if (this.dataset.x === undefined) return new DOMRect(0, 0, 0, 0);
        return new DOMRect(
          Number(this.dataset.x),
          Number(this.dataset.y),
          40,
          40,
        );
      },
    });
    stub("scrollIntoView", { value: scrollIntoView });
    wrapper = mount(Page, { attachTo: document.body });
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    restores.splice(0).forEach((restore) => restore());
  });

  it("moves up and down off a single-row grid", () => {
    el("play").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(el("nav"));

    press("ArrowDown");
    expect(document.activeElement).toBe(el("play"));

    press("ArrowDown");
    expect(document.activeElement).toBe(el("tab"));
  });

  it("leaves moves inside the grid to the grid", () => {
    el("play").focus();

    press("ArrowRight");

    expect(document.activeElement).toBe(el("fav"));
  });

  it("does nothing when no control lies in the direction", () => {
    el("nav").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("nav"));
  });

  it("scrolls a target outside the viewport into view", () => {
    vi.stubGlobal("innerHeight", 400);
    el("play").focus();

    press("ArrowDown");

    expect(scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: "center" }),
    );
    vi.unstubAllGlobals();
  });

  it("skips controls a roving tabindex has taken out of the tab order", () => {
    el("tab").setAttribute("tabindex", "-1");
    el("play").focus();

    expect(press("ArrowDown").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("play"));
  });

  it("leaves the arrows to an open popup's activator", () => {
    el("tab").setAttribute("aria-haspopup", "listbox");
    el("tab").setAttribute("aria-expanded", "true");
    el("tab").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("tab"));
  });

  it("stays out of the way while a game is running", () => {
    storePlaying().setPlaying(true);
    el("play").focus();

    press("ArrowUp");

    expect(document.activeElement).toBe(el("play"));
  });
});
