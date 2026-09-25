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

// happy-dom has no ResizeObserver that fires, so the test lays the grid out.
const resize = vi.hoisted(() => ({ layout: () => {} }));
vi.mock("@vueuse/core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@vueuse/core")>()),
  useResizeObserver: (_target: unknown, callback: () => void) => {
    resize.layout = callback;
  },
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

async function layOut(
  wrapper: Awaited<ReturnType<typeof open>>,
  content: number,
) {
  const value = wrapper.find(".r-v2-about__value").element;
  Object.defineProperty(value, "scrollWidth", { value: content });
  Object.defineProperty(value, "clientWidth", { value: 120 });
  resize.layout();
  await nextTick();
}

describe("AboutDialog", () => {
  beforeEach(() => setActivePinia(createPinia()));

  // Ready before any hover, as RTooltip decides on the pointer's arrival.
  it("shows a value cut off by its tile in a tooltip", async () => {
    const wrapper = await open();

    await layOut(wrapper, 480);

    expect(wrapper.findComponent(RTooltip).props("disabled")).toBe(false);
  });

  it("keeps quiet about a value that fits", async () => {
    const wrapper = await open();

    await layOut(wrapper, 60);

    expect(wrapper.findComponent(RTooltip).props("disabled")).toBe(true);
  });
});
