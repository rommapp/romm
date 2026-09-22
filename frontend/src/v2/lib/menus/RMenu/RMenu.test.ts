import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import RMenu from "./RMenu.vue";

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
});
