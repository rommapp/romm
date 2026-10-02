import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
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
    .map((el) => el.attributes("href") ?? el.classes()[0]);
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

  afterEach(() => wrapper.unmount());

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

  it("follows focus that arrives another way, such as a click", async () => {
    const fav = wrapper.findAll("button.fav")[3].element as HTMLElement;
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
