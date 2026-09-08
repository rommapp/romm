/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { SimpleRom } from "@/stores/roms";
import RandomPickWidget from "./RandomPickWidget.vue";

const { getRandomRom, snackbarError } = vi.hoisted(() => ({
  getRandomRom: vi.fn(),
  snackbarError: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRandomRom },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: snackbarError }),
}));

vi.mock("@v2/lib", () => ({
  RBtn: defineComponent({
    props: { disabled: { type: Boolean, default: false } },
    emits: ["click"],
    template:
      '<button class="reroll" :disabled="disabled" @click="$emit(\'click\')" />',
  }),
  RChip: defineComponent({ template: "<span><slot /></span>" }),
}));

vi.mock("@/v2/components/shared/CachedPlatformIcon.vue", () => ({
  default: defineComponent({ template: "<i />" }),
}));

vi.mock("@/v2/components/shared/GameCover.vue", () => ({
  default: defineComponent({ template: "<figure />" }),
}));

vi.mock("./WidgetCard.vue", () => ({
  default: defineComponent({
    template: "<section><slot name='action' /><slot /></section>",
  }),
}));

function rom(overrides: Partial<SimpleRom> = {}): SimpleRom {
  return {
    id: 42,
    name: "Chrono Trigger",
    fs_name: "chrono-trigger.sfc",
    platform_slug: "snes",
    platform_display_name: "Super Nintendo",
    regions: ["USA"],
    is_identified: true,
    ...overrides,
  } as SimpleRom;
}

function mountWidget() {
  return mount(RandomPickWidget, {
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  });
}

describe("RandomPickWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("resolves a pick with a single request", async () => {
    // Issue #4066: the pick used to cost a count request plus a fetch at a
    // random offset, which got slower the bigger the library was.
    getRandomRom.mockResolvedValue({ data: rom() });

    const wrapper = mountWidget();
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("Chrono Trigger");
  });

  it("shows the empty copy when the library holds no roms", async () => {
    getRandomRom.mockResolvedValue({ data: null });

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-random-pick-empty");
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("shows the error copy without a snackbar on the first pick", async () => {
    getRandomRom.mockRejectedValue(new Error("boom"));

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-random-pick-error");
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("rerolls on demand and keeps the previous pick when the reroll fails", async () => {
    getRandomRom.mockResolvedValue({ data: rom() });

    const wrapper = mountWidget();
    await flushPromises();

    getRandomRom.mockRejectedValue(new Error("boom"));
    await wrapper.get("button.reroll").trigger("click");
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledTimes(2);
    // A failed request says nothing about the library, so the card keeps
    // showing the game it already had and reports through the snackbar.
    expect(wrapper.text()).toContain("Chrono Trigger");
    expect(snackbarError).toHaveBeenCalledTimes(1);
  });
});
