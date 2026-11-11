import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick, ref } from "vue";
import { useCollapsingTitle, useNavTitle } from "./index";

const { notify } = vi.hoisted(() => ({
  notify: { current: (_entries: Partial<IntersectionObserverEntry>[]) => {} },
}));
vi.mock("@vueuse/core", () => ({
  useElementSize: () => ({ height: ref(58) }),
  useIntersectionObserver: (
    _target: unknown,
    callback: typeof notify.current,
  ) => {
    notify.current = callback;
  },
}));

function setup(title = ref("Search")) {
  const wrapper = mount(
    defineComponent({
      setup() {
        useCollapsingTitle(ref(null), title);
        return () => h("h1", title.value);
      },
    }),
  );
  return { wrapper, title };
}

async function observe(bottom: number, isIntersecting = false) {
  notify.current([
    {
      isIntersecting,
      boundingClientRect: new DOMRect(0, bottom - 40, 100, 40),
    },
  ]);
  await nextTick();
}

describe("collapsing navigation title", () => {
  it("appears only after the heading passes above the navigation bar", async () => {
    const { wrapper } = setup();
    const { collapsedTitle } = useNavTitle();
    expect(collapsedTitle.value).toBe("");
    await observe(700);
    expect(collapsedTitle.value).toBe("");
    await observe(58);
    expect(collapsedTitle.value).toBe("Search");
    await observe(90, true);
    expect(collapsedTitle.value).toBe("");
    wrapper.unmount();
  });

  it("updates translated or loaded titles and clears on leaving the page", async () => {
    const { wrapper, title } = setup();
    await observe(30);
    title.value = "Collections";
    await nextTick();
    expect(useNavTitle().collapsedTitle.value).toBe("Collections");
    wrapper.unmount();
    expect(useNavTitle().collapsedTitle.value).toBe("");
  });

  it("does not let an outgoing page clear the incoming title", async () => {
    const old = setup();
    await observe(30);
    const incoming = setup(ref("Platforms"));
    await observe(30);
    old.wrapper.unmount();
    expect(useNavTitle().collapsedTitle.value).toBe("Platforms");
    incoming.wrapper.unmount();
  });
});
