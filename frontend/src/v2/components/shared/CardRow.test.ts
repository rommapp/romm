import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import CardRow from "./CardRow.vue";

vi.mock("vue-i18n");

// happy-dom lays nothing out, so the track's overflow is stubbed.
function overflow(el: Element, scrollWidth: number) {
  Object.defineProperty(el, "clientWidth", { value: 300, configurable: true });
  Object.defineProperty(el, "scrollWidth", {
    value: scrollWidth,
    configurable: true,
  });
}

describe("CardRow overflow", () => {
  let ro: ReturnType<typeof stubResizeObserver>;

  beforeEach(() => {
    ro = stubResizeObserver();
    vi.stubGlobal("requestAnimationFrame", () => 0);
  });

  function render() {
    const cards = ref(1);
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(CardRow, { title: "Row" }, () =>
            Array.from({ length: cards.value }, (_, i) =>
              h("div", { class: "card", key: i }),
            ),
          ),
      }),
      { attachTo: document.body, global: { stubs: { RTag: true } } },
    );
    return { wrapper, cards };
  }

  it("shows the right arrow once a resize makes the track overflow", async () => {
    const { wrapper } = render();
    await nextTick();
    const track = wrapper.get(".card-row__track").element;
    const arrows = () => wrapper.findAll("button").length;
    expect(arrows()).toBe(0);

    overflow(track, 900);
    ro.resize(track, 300);
    await nextTick();

    expect(arrows()).toBe(1);
    wrapper.unmount();
  });

  it("watches cards added after mount", async () => {
    const { wrapper, cards } = render();
    await nextTick();

    cards.value = 3;
    await nextTick();
    // MutationObserver records are delivered as a microtask.
    await Promise.resolve();
    await nextTick();

    const added = wrapper.findAll(".card");
    expect(added).toHaveLength(3);
    expect(added.every((card) => ro.isObserved(card.element))).toBe(true);
    wrapper.unmount();
  });

  it("stops observing on unmount", async () => {
    const { wrapper } = render();
    await nextTick();
    const track = wrapper.get(".card-row__track").element;
    expect(ro.isObserved(track)).toBe(true);

    wrapper.unmount();

    expect(ro.isObserved(track)).toBe(false);
  });
});
