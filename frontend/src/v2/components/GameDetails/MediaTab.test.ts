import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, ref } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import MediaTab from "./MediaTab.vue";

vi.mock("vue-i18n");
vi.mock("@/v2/composables/useRomSync", () => ({
  useRomSync: () => ({ refetchRom: vi.fn() }),
}));
vi.mock("@/v2/composables/useRomSoundtrack", () => ({
  useRomSoundtrack: () => ({
    tracks: ref([]),
    loading: ref(false),
    fallbackArtUrl: ref(null),
  }),
}));

function panelStub(name: string) {
  return {
    __esModule: true,
    default: defineComponent({
      name,
      props: { pdfActive: Boolean },
      setup: () => ({ canUpload: false, openUpload: () => {} }),
      template: `<div />`,
    }),
  };
}
vi.mock("@/v2/components/GameDetails/ManualSubtab.vue", () =>
  panelStub("ManualSubtab"),
);
vi.mock("@/v2/components/GameDetails/WalkthroughSubtab.vue", () =>
  panelStub("WalkthroughSubtab"),
);
vi.mock("@/v2/components/GameDetails/ScreenshotsSubtab.vue", () =>
  panelStub("ScreenshotsSubtab"),
);
vi.mock("@/v2/components/GameDetails/ArtworkSubtab.vue", () =>
  panelStub("ArtworkSubtab"),
);
vi.mock("@/v2/components/Soundtrack/Panel.vue", () =>
  panelStub("SoundtrackPanel"),
);

let router: Router;

async function mountTab(subtab?: string) {
  router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/rom/:id", component: { template: "<div />" } }],
  });
  await router.push({
    path: "/rom/1",
    query: subtab ? { tab: "media", subtab } : { tab: "media" },
  });
  const wrapper = mount(MediaTab, {
    props: {
      rom: makeDetailedRom({ has_soundtrack: false }),
    },
    global: {
      plugins: [router],
      stubs: { SubtabNav: true, RDropzone: true, REmptyState: true },
    },
  });
  await flushPromises();
  return wrapper;
}

function pdfActive(wrapper: Awaited<ReturnType<typeof mountTab>>) {
  return {
    manual: wrapper.findComponent({ name: "ManualSubtab" }).props("pdfActive"),
    walkthrough: wrapper
      .findComponent({ name: "WalkthroughSubtab" })
      .props("pdfActive"),
  };
}

async function selectSubtab(subtab: string) {
  await router.push({ path: "/rom/1", query: { tab: "media", subtab } });
  await flushPromises();
}

describe("MediaTab PDF viewer ownership", () => {
  it("lets only the visited PDF subtab mount a viewer", async () => {
    const wrapper = await mountTab();
    expect(pdfActive(wrapper)).toEqual({ manual: true, walkthrough: false });

    await selectSubtab("walkthrough");
    expect(pdfActive(wrapper)).toEqual({ manual: false, walkthrough: true });
  });

  it("keeps the last PDF subtab's viewer across non-PDF subtabs", async () => {
    const wrapper = await mountTab("walkthrough");
    await selectSubtab("screenshots");
    expect(pdfActive(wrapper)).toEqual({ manual: false, walkthrough: true });
  });

  it("mounts no viewer until a PDF subtab is shown", async () => {
    const wrapper = await mountTab("artwork");
    expect(pdfActive(wrapper)).toEqual({ manual: false, walkthrough: false });
  });
});
