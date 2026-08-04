/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import storePlatforms, { type Platform } from "@/stores/platforms";
import type { SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import PlatformView from "./Platform.vue";

const {
  getRandomRom,
  getRoms,
  getPlatform,
  push,
  snackbarError,
  snackbarInfo,
} = vi.hoisted(() => ({
  getRandomRom: vi.fn(),
  getRoms: vi.fn(),
  getPlatform: vi.fn(),
  push: vi.fn(),
  snackbarError: vi.fn(),
  snackbarInfo: vi.fn(),
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const { routeState } = vi.hoisted(() => ({
  routeState: {
    name: "platform",
    path: "/platform/1",
    params: { platform: "1" } as Record<string, string>,
    query: {} as Record<string, string>,
  },
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => routeState,
  useRouter: () => ({ push, replace: vi.fn() }),
  onBeforeRouteUpdate: vi.fn(),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", UPLOAD: "upload" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRandomRom, getRoms, bulkDownloadRoms: vi.fn() },
}));

vi.mock("@/services/api/platform", () => ({
  default: { getPlatform, deletePlatform: vi.fn() },
}));

vi.mock("@v2/lib", () => ({
  RDivider: defineComponent({ template: "<hr />" }),
}));

vi.mock("@/v2/components/Gallery/GalleryShell.vue", () => ({
  default: defineComponent({
    setup(_props, { expose }) {
      expose({ applyRestoredScroll: vi.fn() });
    },
    template: "<main><slot name='header' /></main>",
  }),
}));

vi.mock("@/v2/components/Gallery/PlatformHead.vue", () => ({
  default: defineComponent({
    emits: ["random"],
    template: `<header><button class="random" @click="$emit('random')" /></header>`,
  }),
}));

vi.mock("@/v2/components/Gallery/FirmwareTab.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Gallery/ScanPlatformDialog.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Gallery/SettingsTab.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/composables/useCan", () => ({
  useCan: () => ref(true),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => vi.fn().mockResolvedValue(false),
}));

vi.mock("@/v2/composables/usePageTitle", () => ({
  usePageTitle: vi.fn(),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: snackbarError, info: snackbarInfo }),
}));

function platform(id: number): Platform {
  return {
    id,
    name: "Super Nintendo",
    display_name: "Super Nintendo",
    slug: "snes",
    fs_slug: "snes",
    rom_count: 83000,
  } as Platform;
}

function rom(id: number): SimpleRom {
  return { id, name: "Chrono Trigger" } as SimpleRom;
}

async function mountView() {
  const platforms = storePlatforms();
  platforms.set([platform(1)]);
  const galleryRoms = storeGalleryRoms();
  vi.spyOn(galleryRoms, "fetchInitialMetadata").mockResolvedValue();

  const wrapper = mount(PlatformView);
  await flushPromises();
  // Only what the button does is under test, not the view's own load flow.
  getRoms.mockClear();
  return wrapper;
}

describe("Platform view random rom", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    getPlatform.mockResolvedValue({ data: platform(1) });
    getRoms.mockResolvedValue({ data: { items: [], total: 0 } });
  });

  it("resolves a pick with a single scoped request", async () => {
    // Issue #4068: the pick used to cost a count request plus a fetch at a
    // random offset, each of them also building the char index, the filter
    // values and the rom id index for the whole platform.
    getRandomRom.mockResolvedValue({ data: rom(42) });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(getRandomRom).toHaveBeenCalledTimes(1);
    expect(getRandomRom).toHaveBeenCalledWith({ platformIds: [1] });
    expect(getRoms).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith({ name: "rom", params: { rom: 42 } });
  });

  it("reports an empty platform without navigating", async () => {
    getRandomRom.mockResolvedValue({ data: null });

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(snackbarInfo).toHaveBeenCalledWith("platform.random-rom-empty");
    expect(push).not.toHaveBeenCalled();
  });

  it("reports a failed pick without navigating", async () => {
    getRandomRom.mockRejectedValue(new Error("boom"));

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await flushPromises();

    expect(snackbarError).toHaveBeenCalledWith("platform.random-rom-error");
    expect(push).not.toHaveBeenCalled();
  });

  it("ignores a click while a pick is in flight", async () => {
    let resolvePick: (value: { data: SimpleRom }) => void = () => {};
    getRandomRom.mockReturnValue(
      new Promise((resolve) => {
        resolvePick = resolve;
      }),
    );

    const wrapper = await mountView();
    await wrapper.get("button.random").trigger("click");
    await wrapper.get("button.random").trigger("click");

    expect(getRandomRom).toHaveBeenCalledTimes(1);

    resolvePick({ data: rom(42) });
    await flushPromises();
    expect(push).toHaveBeenCalledTimes(1);
  });
});
