/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { SimpleRom } from "@/stores/roms";
import AnniversaryWidget from "./AnniversaryWidget.vue";

const { getRoms } = vi.hoisted(() => ({ getRoms: vi.fn() }));

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
  default: { getRoms },
}));

vi.mock("@v2/lib", () => ({
  RBtn: defineComponent({
    props: {
      disabled: { type: Boolean, default: false },
      loading: { type: Boolean, default: false },
      ariaLabel: { type: String, default: "" },
    },
    emits: ["click"],
    template:
      '<button :aria-label="ariaLabel" :disabled="disabled" :data-loading="loading" @click="$emit(\'click\')" />',
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

/** A page of the shared rom list, as `getRoms` resolves it. */
function page(items: SimpleRom[], total = items.length) {
  return { data: { items, total } };
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
  let settle!: (response: ReturnType<typeof page>) => void;
  const promise = new Promise<ReturnType<typeof page>>((resolve) => {
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

  it("asks the shared list for its own local day, one page, no sidecars", async () => {
    getRoms.mockResolvedValue(page([]));

    mountWidget();
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(1);
    expect(getRoms).toHaveBeenCalledWith(
      expect.objectContaining({
        releasedDays: ["9-8"],
        releasedBeforeYear: 2026,
        orderBy: "first_release_date",
        orderDir: "asc",
        offset: 0,
        withTotal: true,
        // Each sidecar is its own scan, and the card renders none of them.
        withCharIndex: false,
        withFilterValues: false,
        withRomIdIndex: false,
      }),
    );
  });

  it("never asks on 1 January, where year-only metadata piles up", async () => {
    vi.setSystemTime(new Date(2026, 0, 1, 12, 0, 0));

    const wrapper = mountWidget();
    await flushPromises();

    expect(getRoms).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("home.widget-anniversaries-empty");
    expect(loadingOf(wrapper)).toBe("false");
  });

  it("shows the oldest anniversary first, with the years elapsed", async () => {
    getRoms.mockResolvedValue(
      page([
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ]),
    );

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("Chrono Trigger");
    expect(wrapper.text()).toContain("home.widget-anniversaries-years");
    expect(wrapper.text()).toContain('{"count":31}');
    expect(wrapper.text()).toContain("1 / 2");
  });

  it("counts the day's real total, not the page it fetched", async () => {
    getRoms.mockResolvedValue(
      page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))], 137),
    );

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("1 / 137");
  });

  it("pages within the fetched page without asking again", async () => {
    getRoms.mockResolvedValue(
      page([
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ]),
    );

    const wrapper = mountWidget();
    await flushPromises();

    await arrows(wrapper).next.trigger("click");
    expect(wrapper.text()).toContain("Super Metroid");
    expect(wrapper.text()).toContain("2 / 2");

    await arrows(wrapper).prev.trigger("click");
    expect(wrapper.text()).toContain("Chrono Trigger");
    expect(getRoms).toHaveBeenCalledTimes(1);
  });

  it("fetches the next page when paging past the loaded ones", async () => {
    getRoms
      .mockResolvedValueOnce(
        page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))], 2),
      )
      .mockResolvedValueOnce(
        page([rom(2, "Super Metroid", releasedOn(2005, 9, 8))], 2),
      );

    const wrapper = mountWidget();
    await flushPromises();
    expect(wrapper.text()).toContain("1 / 2");

    await arrows(wrapper).next.trigger("click");
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(2);
    expect(getRoms).toHaveBeenLastCalledWith(
      // The total came with the first page, so the second does not recount.
      expect.objectContaining({ offset: 1, withTotal: false }),
    );
    expect(wrapper.text()).toContain("Super Metroid");
    expect(wrapper.text()).toContain("2 / 2");
  });

  it("keeps the card when the next page fails, and lets the arrow retry", async () => {
    getRoms
      .mockResolvedValueOnce(
        page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))], 2),
      )
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce(
        page([rom(2, "Super Metroid", releasedOn(2005, 9, 8))], 2),
      );

    const wrapper = mountWidget();
    await flushPromises();

    await arrows(wrapper).next.trigger("click");
    await flushPromises();
    // A failed page says nothing about the game already on screen.
    expect(wrapper.text()).toContain("Chrono Trigger");
    expect(wrapper.text()).not.toContain("home.widget-anniversaries-error");

    await arrows(wrapper).next.trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Super Metroid");
  });

  it("disables each arrow at its end of the day", async () => {
    getRoms.mockResolvedValue(
      page([
        rom(1, "Chrono Trigger", releasedOn(1995, 9, 8)),
        rom(2, "Super Metroid", releasedOn(2005, 9, 8)),
      ]),
    );

    const wrapper = mountWidget();
    await flushPromises();

    expect(arrows(wrapper).prev.attributes("disabled")).toBeDefined();
    expect(arrows(wrapper).next.attributes("disabled")).toBeUndefined();

    await arrows(wrapper).next.trigger("click");

    expect(arrows(wrapper).prev.attributes("disabled")).toBeUndefined();
    expect(arrows(wrapper).next.attributes("disabled")).toBeDefined();
  });

  it("keeps the forward arrow live while its page is in flight", async () => {
    // Disabling it would yank focus mid-page; the spinner rides on the button.
    const first = page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))], 2);
    const second = pending();
    getRoms.mockResolvedValueOnce(first).mockReturnValueOnce(second.promise);

    const wrapper = mountWidget();
    await flushPromises();

    await arrows(wrapper).next.trigger("click");

    expect(arrows(wrapper).next.attributes("disabled")).toBeUndefined();
    expect(arrows(wrapper).next.attributes("data-loading")).toBe("true");

    second.settle(page([rom(2, "Super Metroid", releasedOn(2005, 9, 9))], 2));
    await flushPromises();

    expect(arrows(wrapper).next.attributes("data-loading")).toBe("false");
  });

  it("shows the empty copy when the day has no anniversaries", async () => {
    getRoms.mockResolvedValue(page([]));

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-anniversaries-empty");
  });

  it("shows the error copy when the request fails", async () => {
    getRoms.mockRejectedValue(new Error("boom"));

    const wrapper = mountWidget();
    await flushPromises();

    expect(wrapper.text()).toContain("home.widget-anniversaries-error");
  });

  it("retries a failed load rather than holding the error until midnight", async () => {
    getRoms
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue(
        page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))]),
      );

    const wrapper = mountWidget();
    await flushPromises();
    expect(wrapper.text()).toContain("home.widget-anniversaries-error");

    await vi.advanceTimersByTimeAsync(60_000);
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("Chrono Trigger");
  });

  it("reloads when the local day rolls over, and not before", async () => {
    getRoms.mockResolvedValue(page([]));

    mountWidget();
    await flushPromises();
    expect(getRoms).toHaveBeenCalledWith(
      expect.objectContaining({ releasedDays: ["9-8"] }),
    );

    await vi.advanceTimersByTimeAsync(5 * 60_000);
    expect(getRoms).toHaveBeenCalledTimes(1);

    // A Home page left open overnight would otherwise keep yesterday's games.
    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);
    await flushPromises();

    expect(getRoms).toHaveBeenCalledTimes(2);
    expect(getRoms).toHaveBeenLastCalledWith(
      expect.objectContaining({ releasedDays: ["9-9"] }),
    );
  });

  it("omits the years line for a game released earlier this year", async () => {
    // A client east of the server can ask for a day whose current-year release
    // the server has already counted as past. "0 years ago today" is not a
    // thing, so the line is dropped rather than rendered wrong.
    getRoms.mockResolvedValue(
      page([rom(1, "Brand New Game", releasedOn(2026, 9, 8))]),
    );

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
    getRoms
      .mockReturnValueOnce(yesterday.promise)
      .mockReturnValueOnce(today.promise);

    const wrapper = mountWidget();
    await flushPromises();

    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getRoms).toHaveBeenCalledTimes(2);

    today.settle(page([rom(2, "Super Metroid", releasedOn(2005, 9, 9))]));
    await flushPromises();
    yesterday.settle(page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))]));
    await flushPromises();

    expect(wrapper.text()).toContain("Super Metroid");
    expect(wrapper.text()).not.toContain("Chrono Trigger");
  });

  it("stays loading when a superseded response lands first", async () => {
    const yesterday = pending();
    const today = pending();
    getRoms
      .mockReturnValueOnce(yesterday.promise)
      .mockReturnValueOnce(today.promise);

    const wrapper = mountWidget();
    await flushPromises();

    vi.setSystemTime(new Date(2026, 8, 9, 0, 0, 30));
    await vi.advanceTimersByTimeAsync(60_000);

    // The superseded request settling must not report the new day's request
    // as finished, or the card claims an empty day while it is still loading.
    yesterday.settle(page([rom(1, "Chrono Trigger", releasedOn(1995, 9, 8))]));
    await flushPromises();

    expect(loadingOf(wrapper)).toBe("true");
    expect(wrapper.text()).not.toContain("home.widget-anniversaries-empty");

    today.settle(page([]));
    await flushPromises();

    expect(loadingOf(wrapper)).toBe("false");
  });
});
