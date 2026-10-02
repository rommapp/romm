import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import RMenu from "./RMenu.vue";

const modality = ref<"mouse" | "key">("mouse");
vi.mock("@/v2/composables/useInputModality", () => ({
  useInputModality: () => ({ modality }),
}));

function mountMenu() {
  return mount(RMenu, {
    attachTo: document.body,
    props: { disabled: false },
    slots: {
      activator: `<template #activator="{ props }"><button type="button" class="trigger" v-bind="props">Open</button></template>`,
      default: `<div class="item">Item</div>`,
    },
  });
}

describe("RMenu", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("closes an open menu once it is disabled", async () => {
    const wrapper = mountMenu();
    await wrapper.find("button.trigger").trigger("click");
    await flushPromises();
    expect(document.querySelector('[role="menu"]')).not.toBeNull();

    await wrapper.setProps({ disabled: true });
    await flushPromises();

    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(wrapper.emitted("close")).toHaveLength(1);
    wrapper.unmount();
  });

  // A panel whose content is not RMenuItems (the gallery's letter grid) would
  // otherwise open with nothing focused and no cell for the arrows to leave.
  it("opens on the first `initialFocus` selector that matches", async () => {
    modality.value = "key";
    const wrapper = mount(RMenu, {
      attachTo: document.body,
      props: { initialFocus: [".missing", ".pick-me"] },
      slots: {
        activator: `<template #activator="{ props }"><button type="button" class="trigger" v-bind="props">Open</button></template>`,
        default: `<button type="button" class="skip-me">A</button><button type="button" class="pick-me">B</button>`,
      },
    });

    await wrapper.find("button.trigger").trigger("click");
    await flushPromises();
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => resolve()),
    );

    expect(document.activeElement).toBe(document.querySelector(".pick-me"));
    modality.value = "mouse";
    wrapper.unmount();
  });

  it("anchors to the activator a `v-if` swapped in", async () => {
    const swapped = ref(false);
    const Host = defineComponent({
      components: { RMenu },
      setup: () => ({ swapped }),
      template: `
        <RMenu>
          <template #activator="{ props }">
            <button v-if="!swapped" type="button" class="a" v-bind="props">A</button>
            <button v-else type="button" class="b" v-bind="props">B</button>
          </template>
          <div class="item">Item</div>
        </RMenu>`,
    });
    const wrapper = mount(Host, { attachTo: document.body });
    swapped.value = true;
    await nextTick();
    const activator = wrapper.get("button.b");
    await activator.trigger("click");
    await flushPromises();

    activator.element.dispatchEvent(
      new PointerEvent("pointerdown", { bubbles: true }),
    );
    await flushPromises();

    expect(document.querySelector('[role="menu"]')).not.toBeNull();
    wrapper.unmount();
  });

  describe("openOnHover", () => {
    function mountHoverMenu() {
      return mount(RMenu, {
        attachTo: document.body,
        props: { openOnHover: true },
        slots: {
          activator: `<template #activator="{ props }"><button type="button" class="trigger" v-bind="props">Open</button></template>`,
          default: `<div class="item">Item</div>`,
        },
      });
    }

    async function openByHover() {
      vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
      const wrapper = mountHoverMenu();
      await wrapper.find("button.trigger").trigger("mouseenter");
      await flushPromises();
      expect(document.querySelector('[role="menu"]')).not.toBeNull();
      return wrapper;
    }

    afterEach(() => vi.useRealTimers());

    it("closes a moment after the pointer leaves", async () => {
      const wrapper = await openByHover();

      await wrapper.find("button.trigger").trigger("mouseleave");
      await vi.advanceTimersByTimeAsync(100);
      expect(document.querySelector('[role="menu"]')).not.toBeNull();

      await vi.advanceTimersByTimeAsync(40);
      expect(document.querySelector('[role="menu"]')).toBeNull();
      wrapper.unmount();
    });

    it("stays open when the pointer reaches the panel", async () => {
      const wrapper = await openByHover();

      await wrapper.find("button.trigger").trigger("mouseleave");
      document
        .querySelector('[role="menu"]')!
        .dispatchEvent(new MouseEvent("mouseenter"));
      await vi.advanceTimersByTimeAsync(500);

      expect(document.querySelector('[role="menu"]')).not.toBeNull();
      wrapper.unmount();
    });

    it("drops a pending close on unmount", async () => {
      const wrapper = await openByHover();

      await wrapper.find("button.trigger").trigger("mouseleave");
      wrapper.unmount();
      await vi.advanceTimersByTimeAsync(500);

      expect(wrapper.emitted("close")).toBeUndefined();
    });
  });
});
