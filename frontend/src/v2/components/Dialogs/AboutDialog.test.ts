import { RTooltip } from "@v2/lib";
import { mount } from "@vue/test-utils";
import mitt from "mitt";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick } from "vue";
import type { Events } from "@/types/emitter";
import AboutDialog from "./AboutDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

async function open() {
  const emitter = mitt<Events>();
  const wrapper = mount(AboutDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: defineComponent({
          props: { modelValue: { type: Boolean, default: false } },
          template: `<div v-if="modelValue"><slot name="content" /></div>`,
        }),
      },
    },
  });
  emitter.emit("showAboutDialog", null);
  await nextTick();
  return wrapper;
}

// happy-dom lays nothing out, so each value's widths are set by hand.
function widths(wrapper: Awaited<ReturnType<typeof open>>, content: number) {
  const value = wrapper.find(".r-v2-about__value").element;
  Object.defineProperty(value, "scrollWidth", { value: content });
  Object.defineProperty(value, "clientWidth", { value: 120 });
}

describe("AboutDialog", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("shows a value cut off by its tile in a tooltip", async () => {
    const wrapper = await open();
    widths(wrapper, 480);

    await wrapper.find(".r-v2-about__tile").trigger("mouseenter");

    expect(wrapper.findComponent(RTooltip).props("disabled")).toBe(false);
  });

  it("keeps quiet about a value that fits", async () => {
    const wrapper = await open();
    widths(wrapper, 60);

    await wrapper.find(".r-v2-about__tile").trigger("mouseenter");

    expect(wrapper.findComponent(RTooltip).props("disabled")).toBe(true);
  });
});
