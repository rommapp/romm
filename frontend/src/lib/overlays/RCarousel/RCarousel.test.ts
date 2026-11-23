import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import RCarousel from "./RCarousel.vue";

function press(key: string) {
  window.dispatchEvent(new KeyboardEvent("keydown", { key }));
}

function mountCarousel(fullscreen: boolean) {
  return mount(RCarousel, {
    props: { items: ["a", "b", "c"], modelValue: 0, fullscreen },
    global: { stubs: { teleport: true } },
  });
}

describe("RCarousel window keys", () => {
  it("leaves window keys alone while inline", async () => {
    const wrapper = mountCarousel(false);
    await nextTick();

    press("ArrowRight");
    press("Escape");

    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
    expect(wrapper.emitted("close")).toBeUndefined();
  });

  it("follows the fullscreen prop as it changes", async () => {
    const wrapper = mountCarousel(false);
    await nextTick();

    await wrapper.setProps({ fullscreen: true });
    press("ArrowRight");
    press("Escape");
    expect(wrapper.emitted("update:modelValue")).toEqual([[1]]);
    expect(wrapper.emitted("close")).toHaveLength(1);

    await wrapper.setProps({ fullscreen: false });
    press("Escape");
    expect(wrapper.emitted("close")).toHaveLength(1);
  });

  it("stops listening once unmounted", async () => {
    const onClose = vi.fn();
    const wrapper = mount(RCarousel, {
      props: { items: ["a", "b"], modelValue: 0, fullscreen: true, onClose },
      global: { stubs: { teleport: true } },
    });
    await nextTick();
    press("Escape");
    expect(onClose).toHaveBeenCalledOnce();

    wrapper.unmount();
    press("Escape");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
