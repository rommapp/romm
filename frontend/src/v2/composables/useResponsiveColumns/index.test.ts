import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { stubResizeObserver } from "@/test-utils/resizeObserver";
import { useResponsiveColumns } from "./index";

let observer: ReturnType<typeof stubResizeObserver>;
let layout: ReturnType<typeof useResponsiveColumns>;
const cardWidth = ref(158);

const Host = defineComponent({
  props: { swapped: { type: Boolean, default: false } },
  setup(props) {
    const el = ref<HTMLElement | null>(null);
    layout = useResponsiveColumns(el, { cardWidth: () => cardWidth.value });
    return () => h(props.swapped ? "section" : "div", { ref: el });
  },
});

async function mountHost() {
  const wrapper = mount(Host);
  // The observer binds once the template ref lands.
  await nextTick();
  return wrapper;
}

describe("useResponsiveColumns", () => {
  beforeEach(() => {
    observer = stubResizeObserver();
    cardWidth.value = 158;
  });

  it("derives the column count from the observed width", async () => {
    const wrapper = await mountHost();

    // floor((700 + 12) / (158 + 12)) = 4
    observer.resize(wrapper.element, 700);
    expect(layout.columns.value).toBe(4);
    expect(layout.usableWidth.value).toBe(700);

    observer.resize(wrapper.element, 340);
    expect(layout.columns.value).toBe(2);
  });

  it("recomputes from the last width when a reactive option changes", async () => {
    const wrapper = await mountHost();
    observer.resize(wrapper.element, 700);

    cardWidth.value = 100;
    await nextTick();

    // floor((700 + 12) / (100 + 12)) = 6
    expect(layout.columns.value).toBe(6);
  });

  it("follows the bound element when it is swapped", async () => {
    const wrapper = await mountHost();
    const first = wrapper.element;

    await wrapper.setProps({ swapped: true });
    await nextTick();
    const second = wrapper.element;

    expect(second).not.toBe(first);
    expect(observer.isObserved(first)).toBe(false);
    observer.resize(second, 340);
    expect(layout.columns.value).toBe(2);
  });

  it("stops observing once unmounted", async () => {
    const wrapper = await mountHost();
    const el = wrapper.element;
    expect(observer.isObserved(el)).toBe(true);

    wrapper.unmount();

    expect(observer.isObserved(el)).toBe(false);
  });
});
