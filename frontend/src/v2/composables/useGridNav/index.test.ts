import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  defineComponent,
  h,
  nextTick,
  ref,
  type Ref,
  type VNodeChild,
} from "vue";
import { useGridNav } from "./index";

// useGridNav reads the input modality and the current route; stub both so
// the composable can run outside a real app shell. Modality stays "mouse"
// so the pad-only autofocus never fires and steals focus mid-test.
vi.mock("@/v2/composables/useInputModality", () => ({
  useInputModality: () => ({ modality: ref("mouse") }),
}));
vi.mock("vue-router", () => ({
  useRoute: () => ({ fullPath: "/test" }),
}));

// Resolve after the composable's coalescing rAF has fired.
const raf = () =>
  new Promise<void>((res) => requestAnimationFrame(() => res()));

// Mount a `<section>` wired to useGridNav around caller-supplied children.
// A single component definition keeps `vue/one-component-per-file` happy.
function mountHost(children: () => VNodeChild[]) {
  const Host = defineComponent({
    setup() {
      const root = ref<HTMLElement | null>(null) as Ref<HTMLElement | null>;
      useGridNav(root, { rowSelector: ".row" });
      return { root };
    },
    render() {
      return h("section", { ref: "root" }, children());
    },
  });
  return mount(Host, { attachTo: document.body });
}

// A grid host: one row per entry in `shape`, that many cards in it. Each
// card is an <a> wrapping a hidden overlay <button> (mirrors GameCard's
// hover-overlay actions — focusable even while invisible).
function mountGrid(shape: number[]) {
  return mountHost(() =>
    shape.map((count, r) =>
      h(
        "div",
        { class: "row" },
        Array.from({ length: count }, (_, c) =>
          h(
            "a",
            { href: "#", class: "card", "data-focus-key": `k-${r}-${c}` },
            [h("button", { class: "overlay" }, "action")],
          ),
        ),
      ),
    ),
  );
}

// A single row of two cards; the first carries two overlay actions so we
// can move between them.
function mountCards() {
  return mountHost(() => [
    h("div", { class: "row" }, [
      h("a", { href: "#", class: "card", "data-focus-key": "k-0-0" }, [
        h("button", { class: "overlay", "data-act": "a" }, "a"),
        h("button", { class: "overlay", "data-act": "b" }, "b"),
      ]),
      h("a", { href: "#", class: "card", "data-focus-key": "k-0-1" }, []),
    ]),
  ]);
}

function focusables(root: Element) {
  return Array.from(root.querySelectorAll<HTMLElement>(".card, .overlay"));
}
function tabStops(root: Element) {
  return focusables(root).filter((el) => el.getAttribute("tabindex") === "0");
}

beforeEach(() => {
  setActivePinia(createPinia());
  // happy-dom doesn't implement scrollIntoView on elements.
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("useGridNav roving tabindex", () => {
  it("makes the whole grid a single tab stop on mount", async () => {
    const wrapper = mountGrid([3, 3]);
    await nextTick();
    await raf();

    const root = wrapper.element as HTMLElement;
    const stops = tabStops(root);
    // Exactly one tabbable element across 6 cards + 6 overlay buttons.
    expect(stops).toHaveLength(1);
    // ...and it's the first card, not an overlay button.
    expect(stops[0].classList.contains("card")).toBe(true);
    expect(stops[0].getAttribute("data-focus-key")).toBe("k-0-0");
    expect(stops[0].hasAttribute("data-grid-nav-cell")).toBe(true);

    // Every other focusable — including the active card's own overlay
    // button — is out of the tab order.
    for (const el of focusables(root)) {
      if (el === stops[0]) continue;
      expect(el.getAttribute("tabindex")).toBe("-1");
    }
    wrapper.unmount();
  });

  it("moves the single tab stop with arrow keys", async () => {
    const wrapper = mountGrid([3, 3]);
    await nextTick();
    await raf();
    const root = wrapper.element as HTMLElement;

    const firstCard = root.querySelector<HTMLElement>(
      '[data-focus-key="k-0-0"]',
    )!;
    firstCard.focus();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    await nextTick();

    const stops = tabStops(root);
    expect(stops).toHaveLength(1);
    expect(stops[0].getAttribute("data-focus-key")).toBe("k-0-1");
    expect(document.activeElement).toBe(stops[0]);
    wrapper.unmount();
  });

  it("re-establishes a single tab stop after new rows mount", async () => {
    const wrapper = mountGrid([2]);
    await nextTick();
    await raf();
    const root = wrapper.element as HTMLElement;

    // Append a fresh row straight into the DOM (as the virtualiser does
    // when the user scrolls) — its cards arrive as natural tab stops
    // until the mutation observer re-syncs.
    const newRow = document.createElement("div");
    newRow.className = "row";
    newRow.innerHTML =
      '<a href="#" class="card" data-focus-key="k-9-0"><button class="overlay">action</button></a>';
    root.appendChild(newRow);
    // One frame for the mutation observer to fire scheduleRefresh, another
    // for the refresh's own coalescing rAF to run syncRoving.
    await raf();
    await raf();

    expect(tabStops(root)).toHaveLength(1);
    // The new card is demoted like every other non-active cell.
    const newCard = root.querySelector<HTMLElement>(
      '[data-focus-key="k-9-0"]',
    )!;
    expect(newCard.getAttribute("tabindex")).toBe("-1");
    expect(newCard.querySelector(".overlay")!.getAttribute("tabindex")).toBe(
      "-1",
    );
    wrapper.unmount();
  });
});

describe("useGridNav card action row", () => {
  it("ContextMenu drops focus into the card's actions; arrows move between them", async () => {
    const wrapper = mountCards();
    await nextTick();
    await raf();
    const root = wrapper.element as HTMLElement;

    const card = root.querySelector<HTMLElement>('[data-focus-key="k-0-0"]')!;
    card.focus();

    // ContextMenu → focus the first overlay action.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ContextMenu" }));
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-act"),
    ).toBe("a");

    // Back to the card, then Space (the cross-platform trigger) → actions.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    window.dispatchEvent(new KeyboardEvent("keydown", { key: " " }));
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-act"),
    ).toBe("a");

    // ArrowRight → next action; the card→card nav must NOT fire.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-act"),
    ).toBe("b");

    // Escape → back to the card link.
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-focus-key"),
    ).toBe("k-0-0");
    wrapper.unmount();
  });

  it("gamepad X descends into the card's actions", async () => {
    const wrapper = mountCards();
    await nextTick();
    await raf();
    const root = wrapper.element as HTMLElement;

    root.querySelector<HTMLElement>('[data-focus-key="k-0-0"]')!.focus();
    window.dispatchEvent(
      new CustomEvent("gamepad:buttondown", { detail: { name: "x" } }),
    );
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-act"),
    ).toBe("a");
    wrapper.unmount();
  });
});
