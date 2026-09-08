/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { SimpleRom } from "@/stores/roms";
import AnniversaryWidget from "./AnniversaryWidget.vue";

const { getAnniversaryRoms } = vi.hoisted(() => ({
  getAnniversaryRoms: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, named?: Record<string, unknown>) =>
      named ? `${key}:${JSON.stringify(named)}` : key,
  }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getAnniversaryRoms },
}));

vi.mock("@v2/lib", () => ({
  RBtn: defineComponent({
    props: {
      disabled: { type: Boolean, default: false },
      ariaLabel: { type: String, default: "" },
    },
    emits: ["click"],
    template:
      '<button :aria-label="ariaLabel" :disabled="disabled" @click="$emit(\'click\')" />',
  }),
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

/** UTC midnight of a release date, the unit `first_release_date` is stored in. */
function releasedOn(year: number, month: number, day: number): number {
  return Date.UTC(year, month - 1, day);
}

function rom(id: number, name: string, released: number): SimpleRom {
  return {
    id,
    name,
    fs_name: `${name}.sfc`,
    platform_slug: "snes",
    platform_display_name: "Super Nintendo",
    is_identified: true,
    metadatum: { first_release_date: released },
  } as unknown as SimpleRom;
}

function mountWidget() {
  return mount(AnniversaryWidget, {
    global: { stubs: { RouterLink: { template: "<a><slot /></a>" } } },
  });
}

function arrows(wrapper: ReturnType<typeof mountWidget>) {
  const buttons = wrapper.findAll("button");
  return { prev: buttons[0], next: buttons[1] };
}

describe("AnniversaryWidget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 8 September 2026, local time, so the request is asserted against a
    // known calendar day rather than whenever the suite happens to run.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 8, 8, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("asks for the client's own local month and day", async () => {
    getAnniversaryRoms.mockResolvedValue({ data: [] });

    mountWidget();
    await flushPromises();

    expect(getAnniversaryRoms).toHaveBeenCalledTimes(1);
    expect(getAnniversaryRoms).toHaveBeenCalledWith({ month: 9, day: 8 });
  });

  it("shows the oldest anniversary first, with the years elapsed", async () => {
    getAnniversaryRoms.mockResolvedValue({
      data: [
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ],
    });

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("Chrono Trigger");
    expect(wrapper.text()).toContain("home.widget-anniversaries-years");
    expect(wrapper.text()).toContain('{"count":31}');
    expect(wrapper.text()).toContain("1 / 2");
  });

  it("pages forward and back through the day's games", async () => {
    getAnniversaryRoms.mockResolvedValue({
      data: [
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ],
    });

    const wrapper = mountWidget();
    await flushPromises();

    await arrows(wrapper).next.trigger("click");
    expect(wrapper.text()).toContain("Super Metroid");
    expect(wrapper.text()).toContain("2 / 2");

    await arrows(wrapper).prev.trigger("click");
    expect(wrapper.text()).toContain("Chrono Trigger");
    // Paging is client-side over the fetched list, so no extra requests.
    expect(getAnniversaryRoms).toHaveBeenCalledTimes(1);
  });

  it("disables each arrow at its end of the list", async () => {
    getAnniversaryRoms.mockResolvedValue({
      data: [
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ],
    });

    const wrapper = mountWidget();
    await flushPromises();

    expect(arrows(wrapper).prev.attributes("disabled")).toBeDefined();
    expect(arrows(wrapper).next.attributes("disabled")).toBeUndefined();

    await arrows(wrapper).next.trigger("click");

    expect(arrows(wrapper).prev.attributes("disabled")).toBeUndefined();
    expect(arrows(wrapper).next.attributes("disabled")).toBeDefined();
  });

  it("shows the empty copy when the day has no anniversaries", async () => {
    getAnniversaryRoms.mockResolvedValue({ data: [] });

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-anniversaries-empty");
  });

  it("shows the error copy when the request fails", async () => {
    getAnniversaryRoms.mockRejectedValue(new Error("boom"));

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-anniversaries-error");
  });

  it("omits the years line for a game released earlier this year", async () => {
    // A client east of the server can ask for a day whose current-year release
    // the server has already counted as past. "0 years ago today" is not a
    // thing, so the line is dropped rather than rendered wrong.
    getAnniversaryRoms.mockResolvedValue({
      data: [rom(1, "Brand New Game", releasedOn(2026, 9, 8))],
    });

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("Brand New Game");
    expect(wrapper.text()).not.toContain("home.widget-anniversaries-years");
  });
});
