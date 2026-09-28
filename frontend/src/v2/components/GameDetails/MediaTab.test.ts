import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import MediaTab from "./MediaTab.vue";

const query = ref<Record<string, string>>({});

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({
    get query() {
      return query.value;
    },
  }),
  useRouter: () => ({
    replace: vi.fn(async ({ query: next }) => {
      query.value = next;
    }),
    push: vi.fn(),
  }),
}));
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

async function mountTab(subtab?: string) {
  query.value = subtab ? { tab: "media", subtab } : { tab: "media" };
  const wrapper = mount(MediaTab, {
    props: {
      rom: makeDetailedRom({ has_soundtrack: false }),
    },
    global: { stubs: { SubtabNav: true, RDropzone: true, REmptyState: true } },
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
  query.value = { tab: "media", subtab };
  await nextTick();
  await flushPromises();
}

describe("MediaTab PDF viewer ownership", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

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
