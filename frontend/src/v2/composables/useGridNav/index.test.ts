/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import storeFocusRestoration from "@/v2/stores/focusRestoration";
import { useGridNav } from "./index";

vi.mock("vue-router", () => ({ useRoute: () => ({ fullPath: "/gallery" }) }));

// Two rows of two cells; each cell holds a link, a button, and a control
// its component already took out of the tab order.
const Grid = defineComponent({
  setup() {
    const root = ref<HTMLElement | null>(null);
    useGridNav(root, { rowSelector: ".row", roving: true });
    const cell = (id: number) =>
      h("div", { class: "cell", role: "gridcell" }, [
        h("a", { href: `/rom/${id}`, "data-focus-key": `rom-${id}` }, "Game"),
        h("button", { class: "fav" }, "Favorite"),
        h("button", { class: "skip", tabindex: "-1" }, "Skip"),
      ]);
    return () =>
      h("div", { ref: root, role: "grid" }, [
        h("div", { class: "row", role: "row" }, [cell(1), cell(2)]),
        h("div", { class: "row", role: "row" }, [cell(3), cell(4)]),
      ]);
  },
});

function tabbable(wrapper: ReturnType<typeof mount>): string[] {
  return wrapper
    .findAll("a, button")
    .filter((el) => el.attributes("tabindex") !== "-1")
    .map((el) => el.attributes("href") ?? el.classes()[0]!);
}

function focusLink(id: number) {
  (document.querySelector(`a[href='/rom/${id}']`) as HTMLElement).focus();
}

function press(key: string, init: KeyboardEventInit = {}) {
  document.dispatchEvent(new KeyboardEvent("keydown", { key, ...init }));
}

function focusedHref(): string | null | undefined {
  return document.activeElement?.getAttribute("href");
}

async function frame() {
  await new Promise((resolve) => requestAnimationFrame(resolve));
  await nextTick();
}

describe("useGridNav roving", () => {
  let wrapper: ReturnType<typeof mount>;

  beforeEach(async () => {
    wrapper = mount(Grid, { attachTo: document.body });
    await frame();
  });

  it("leaves only the first cell's controls in the tab order", () => {
    expect(tabbable(wrapper)).toEqual(["/rom/1", "fav"]);
  });

  it("moves the tab stop with the arrow keys", async () => {
    (wrapper.get("a[href='/rom/1']").element as HTMLElement).focus();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown" }));
    await nextTick();

    expect(document.activeElement?.getAttribute("href")).toBe("/rom/3");
    expect(tabbable(wrapper)).toEqual(["/rom/3", "fav"]);
  });

  it("asks for a visible focus ring on the cell it moves to", () => {
    const { setModality } = useInputModality();
    setModality("key");
    onTestFinished(() => setModality("mouse"));
    focusLink(1);
    const focus = vi.spyOn(
      wrapper.get("a[href='/rom/3']").element as HTMLElement,
      "focus",
    );

    press("ArrowDown");

    expect(focus).toHaveBeenCalledWith(
      expect.objectContaining({ focusVisible: true }),
    );
  });

  it("follows focus that arrives another way, such as a click", async () => {
    const fav = wrapper.findAll("button.fav")[3]!.element as HTMLElement;
    fav.focus();
    // happy-dom's focus() fires no focusin.
    fav.dispatchEvent(new FocusEvent("focusin", { bubbles: true }));
    await nextTick();

    expect(tabbable(wrapper)).toEqual(["/rom/4", "fav"]);
  });

  it("moves to the row's ends on Home and End", async () => {
    focusLink(1);
    press("End");
    expect(focusedHref()).toBe("/rom/2");
    press("Home");
    expect(focusedHref()).toBe("/rom/1");
  });

  it("moves to the grid's ends on Ctrl+Home and Ctrl+End", async () => {
    focusLink(1);
    press("End", { ctrlKey: true });
    await frame();
    await frame();
    expect(focusedHref()).toBe("/rom/4");
    press("Home", { ctrlKey: true });
    await frame();
    await frame();
    expect(focusedHref()).toBe("/rom/1");
  });

  it("keeps the column on PageDown and PageUp", async () => {
    focusLink(2);
    press("PageDown");
    expect(focusedHref()).toBe("/rom/4");
    press("PageUp");
    expect(focusedHref()).toBe("/rom/2");
  });

  it("never puts a control its component excluded back in the order", async () => {
    (wrapper.get("a[href='/rom/2']").element as HTMLElement).focus();
    await nextTick();

    expect(
      wrapper.findAll("button.skip").map((el) => el.attributes("tabindex")),
    ).toEqual(["-1", "-1", "-1", "-1"]);
  });
});

describe("useGridNav autofocus", () => {
  const { setModality } = useInputModality();
  const rows = ref(0);

  // Rows that arrive after mount, as a fetch resolving would add them.
  const LateGrid = defineComponent({
    setup() {
      const root = ref<HTMLElement | null>(null);
      useGridNav(root, { rowSelector: ".row" });
      return () =>
        h(
          "div",
          { ref: root },
          Array.from({ length: rows.value }, (_, row) =>
            h("div", { class: "row" }, [
              h("a", { href: `/rom/${row + 1}` }, "Game"),
            ]),
          ),
        );
    },
  });

  afterEach(() => {
    rows.value = 0;
    setModality("mouse");
  });

  it("lands pad focus on the first cell once late rows arrive", async () => {
    setModality("pad");
    mount(LateGrid, { attachTo: document.body });
    await frame();
    expect(focusedHref()).toBeNull();

    rows.value = 2;
    await frame();

    expect(focusedHref()).toBe("/rom/1");
  });
});

const TILE = 100;

// Two rows of two tiles, laid out by the data attributes since jsdom has no
// layout engine.
const WrapGrid = defineComponent({
  setup() {
    const root = ref<HTMLElement | null>(null);
    useGridNav(root, { cellSelector: ".cell" });
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
              "data-focus-key": `${row}-${col}`,
            }),
          ),
        ),
      );
  },
});

describe("useGridNav on a wrapping grid", () => {
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

  function press(key: string, init: KeyboardEventInit = {}) {
    document.activeElement!.dispatchEvent(
      new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
        ...init,
      }),
    );
  }

  beforeEach(() => {
    setModality("mouse");
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
    wrapper = mount(WrapGrid, { attachTo: document.body });
  });

  afterEach(() => {
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

  it("asks for a visible focus ring on the tile it moves to", () => {
    setModality("key");
    cell(1, 0).focus();
    const focus = vi.spyOn(cell(0, 0), "focus");

    press("ArrowUp");

    expect(focus).toHaveBeenCalledWith(
      expect.objectContaining({ focusVisible: true }),
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

  it("jumps to a row's ends and, with Ctrl, the grid's", () => {
    cell(1, 1).focus();

    press("Home");
    expect(document.activeElement).toBe(cell(1, 0));

    press("Home", { ctrlKey: true });
    expect(document.activeElement).toBe(cell(0, 0));
  });

  it("reaches the grid's ends through tiles it already visited", () => {
    cell(0, 0).focus();
    press("ArrowRight");
    press("ArrowLeft");
    press("ArrowRight");
    press("ArrowDown");

    press("Home", { ctrlKey: true });
    expect(document.activeElement).toBe(cell(0, 0));

    press("ArrowDown");
    press("ArrowRight");
    press("ArrowUp");
    press("End", { ctrlKey: true });
    expect(document.activeElement).toBe(cell(1, 1));
  });

  it("centres the restored tile when the pad takes over", async () => {
    storeFocusRestoration().save("/gallery", "1-1");

    setModality("pad");
    await nextTick();

    expect(document.activeElement).toBe(cell(1, 1));
    expect(scrollIntoView).toHaveBeenLastCalledWith(
      expect.objectContaining({ block: "center" }),
    );
  });
});

describe("useGridNav on a wrapping grid, autofocus", () => {
  const { setModality } = useInputModality();
  const tiles = ref(0);

  // Tiles that arrive after mount, as a fetch resolving would add them.
  const LateGrid = defineComponent({
    setup() {
      const root = ref<HTMLElement | null>(null);
      useGridNav(root, { cellSelector: ".cell" });
      return () =>
        h(
          "div",
          { ref: root },
          Array.from({ length: tiles.value }, (_, i) =>
            h("button", { class: "cell", "data-focus-key": `tile-${i}` }),
          ),
        );
    },
  });

  afterEach(() => {
    tiles.value = 0;
    setModality("mouse");
  });

  it("lands pad focus on the first tile once late tiles arrive", async () => {
    setModality("pad");
    const wrapper = mount(LateGrid, { attachTo: document.body });
    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(document.activeElement).toBe(document.body);

    tiles.value = 2;
    await nextTick();
    await Promise.resolve();

    expect(document.activeElement).toBe(wrapper.find(".cell").element);
  });
});
