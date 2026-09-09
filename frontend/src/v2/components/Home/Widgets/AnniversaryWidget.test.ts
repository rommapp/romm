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
    props: { loading: { type: Boolean, default: false } },
    // Mirrors the real card, which swaps the body out for a spinner.
    template:
      "<section :data-loading='loading'><slot name='action' /><slot v-if='!loading' /></section>",
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

/** A request the test settles by hand, so two can be in flight at once. */
function pending() {
  let settle!: (response: { data: SimpleRom[] }) => void;
  const promise = new Promise<{ data: SimpleRom[] }>((resolve) => {
    settle = resolve;
  });
  return { promise, settle };
}

function loadingOf(wrapper: ReturnType<typeof mountWidget>) {
  return wrapper.find("section").attributes("data-loading");
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

  it("retries a failed load rather than holding the error until midnight", async () => {
    getAnniversaryRoms
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({
        data: [rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))],
      });

    const wrapper = mountWidget();
    await flushPromises();
    expect(wrapper.text()).toContain("home.widget-anniversaries-error");

    await vi.advanceTimersByTimeAsync(60_000);
    await flushPromises();

    expect(getAnniversaryRoms).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("Chrono Trigger");
  });

  it("reloads when the local day rolls over, and not before", async () => {
    getAnniversaryRoms.mockResolvedValue({ data: [] });

    mountWidget();
    await flushPromises();
    expect(getAnniversaryRoms).toHaveBeenCalledWith({ month: 9, day: 8 });

    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(getAnniversaryRoms).toHaveBeenCalledTimes(1);

    // A Home page left open overnight would otherwise keep yesterday's games.
    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);
    await flushPromises();

    expect(getAnniversaryRoms).toHaveBeenCalledTimes(2);
    expect(getAnniversaryRoms).toHaveBeenLastCalledWith({ month: 9, day: 9 });
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

  it("ignores a response the day rollover has already superseded", async () => {
    // A request that spans local midnight can land after the new day's. It
    // must not commit yesterday's games, because the rollover has already
    // marked the day loaded and so will not ask again for another 24 hours.
    const yesterday = pending();
    const today = pending();
    getAnniversaryRoms
      .mockReturnValueOnce(yesterday.promise)
      .mockReturnValueOnce(today.promise);

    const wrapper = mountWidget();
    await flushPromises();

    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getAnniversaryRoms).toHaveBeenCalledTimes(2);

    today.settle({ data: [rom(2, "Super Metroid", releasedOn(2005, 9, 9))] });
    await flushPromises();
    yesterday.settle({
      data: [rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))],
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Super Metroid");
    expect(wrapper.text()).not.toContain("Chrono Trigger");
  });

  it("stays loading when a superseded response lands first", async () => {
    const yesterday = pending();
    const today = pending();
    getAnniversaryRoms
      .mockReturnValueOnce(yesterday.promise)
      .mockReturnValueOnce(today.promise);

    const wrapper = mountWidget();
    await flushPromises();

    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);

    // The superseded request settling must not report the new day's request
    // as finished, or the card claims an empty day while it is still loading.
    yesterday.settle({
      data: [rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))],
    });
    await flushPromises();

    expect(loadingOf(wrapper)).toBe("true");
    expect(wrapper.text()).not.toContain("home.widget-anniversaries-empty");

    today.settle({ data: [] });
    await flushPromises();

    expect(loadingOf(wrapper)).toBe("false");
  });
});
