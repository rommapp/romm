import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import AlphaStrip from "./AlphaStrip.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function mountStrip(props: Record<string, unknown>) {
  return mount(AlphaStrip, { props, attachTo: document.body });
}

// tabindex of the button for a given letter ("" when the attribute is
// absent, i.e. a disabled/unavailable letter).
function tabindexOf(wrapper: ReturnType<typeof mountStrip>, letter: string) {
  return wrapper.get(`[data-letter="${letter}"]`).attributes("tabindex") ?? "";
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("AlphaStrip keyboard roving", () => {
  it("exposes a single tab stop; unavailable letters aren't focusable", () => {
    const wrapper = mountStrip({ available: ["A", "C", "F"] });

    // First available letter is the lone tab stop; the rest are -1.
    expect(tabindexOf(wrapper, "A")).toBe("0");
    expect(tabindexOf(wrapper, "C")).toBe("-1");
    expect(tabindexOf(wrapper, "F")).toBe("-1");
    // Unavailable letters carry no tabindex (they're disabled).
    expect(tabindexOf(wrapper, "B")).toBe("");
    wrapper.unmount();
  });

  it("puts the tab stop on the current (scroll-spied) letter", () => {
    const wrapper = mountStrip({ available: ["A", "C", "F"], current: "C" });

    expect(tabindexOf(wrapper, "A")).toBe("-1");
    expect(tabindexOf(wrapper, "C")).toBe("0");
    wrapper.unmount();
  });

  it("moves between available letters with Arrow keys, skipping gaps", async () => {
    const wrapper = mountStrip({ available: ["A", "C", "F"] });
    const btnA = wrapper.get('[data-letter="A"]');
    (btnA.element as HTMLElement).focus();

    await btnA.trigger("keydown", { key: "ArrowDown" });
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-letter"),
    ).toBe("C");
    expect(tabindexOf(wrapper, "C")).toBe("0");
    expect(tabindexOf(wrapper, "A")).toBe("-1");

    await wrapper.get('[data-letter="C"]').trigger("keydown", { key: "End" });
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-letter"),
    ).toBe("F");

    await wrapper
      .get('[data-letter="F"]')
      .trigger("keydown", { key: "ArrowUp" });
    expect(
      (document.activeElement as HTMLElement).getAttribute("data-letter"),
    ).toBe("C");
    wrapper.unmount();
  });
});
