import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
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
});
