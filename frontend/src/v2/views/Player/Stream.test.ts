import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { SaveSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import AssetPreview from "@/v2/components/Player/AssetPreview.vue";
import SaveDataPanel from "@/v2/components/Player/SaveDataPanel.vue";
import AssetList from "@/v2/components/shared/AssetList.vue";
import Stream from "./Stream.vue";

const mocks = vi.hoisted(() => ({
  claimSession: vi.fn(),
  fetchConfig: vi.fn(),
  getRom: vi.fn(),
  container: null as Record<string, unknown> | null,
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
  useRoute: () => ({ params: { rom: "3" }, query: {} }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ROM: "rom", PLATFORM: "platform" },
}));

vi.mock("@/services/api/rom", () => ({
  default: { getRom: mocks.getRom },
}));

vi.mock("@/services/api/streaming", () => ({
  default: {},
  isMemoryCardImportDetail: () => false,
}));

vi.mock("@/stores/auth", () => ({
  default: () => ({ user: { id: 1 }, scopes: [] }),
}));

vi.mock("@/stores/playing", () => ({
  default: () => ({ setPlaying: vi.fn(), setStageActive: vi.fn() }),
}));

vi.mock("@/stores/roms", () => ({
  default: () => ({ currentRom: null }),
}));

vi.mock("@/v2/stores/galleryRoms", () => ({
  default: () => ({ getRomById: () => null }),
}));

vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({
    claimSession: mocks.claimSession,
    containerForPlatform: () => mocks.container,
    platformCapabilities: () => ({}),
    fetchConfig: mocks.fetchConfig,
    fetchSessionStatus: vi.fn(),
    forgetJoinableSession: vi.fn(),
    heartbeatSession: vi.fn(),
    joinSession: vi.fn(),
    releaseSession: vi.fn(),
    releaseSessionKeepalive: vi.fn(),
    saveAndExit: vi.fn(),
    saveAndExitKeepalive: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useActivityPresence", () => ({
  useActivityPresence: () => ({
    start: vi.fn(),
    stopHeartbeat: vi.fn(),
    emitStop: vi.fn(),
    stop: vi.fn(),
  }),
}));

vi.mock("@/v2/composables/useBackgroundArt", () => ({
  useBackgroundArt: () => vi.fn(),
}));

vi.mock("@/v2/composables/useCoverArt", async () => {
  const { computed } = await import("vue");
  return {
    useCoverArt: () => ({
      style: computed(() => "cover_path"),
      coverUrl: computed(() => null),
      fallbackUrl: computed(() => null),
    }),
  };
});

vi.mock("@/v2/composables/useFullscreenPref", async () => {
  const { ref } = await import("vue");
  return { useFullscreenPref: () => ({ fullscreenOnPlay: ref(false) }) };
});

vi.mock("@/v2/composables/useMultiplayerPref", async () => {
  const { ref } = await import("vue");
  return { useMultiplayerPref: () => ({ multiplayerOnPlay: ref(false) }) };
});

vi.mock("@/v2/composables/useInputModality", async () => {
  const { ref } = await import("vue");
  return { useInputModality: () => ({ modality: ref("mouse") }) };
});

vi.mock("@/v2/composables/usePageTitle", () => ({ usePageTitle: vi.fn() }));

vi.mock("@/v2/composables/usePlaySession", () => ({
  usePlaySession: () => ({ start: vi.fn(), flush: vi.fn() }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: vi.fn(),
}));

vi.mock("@/v2/composables/useStageActive", () => ({
  useStageActive: vi.fn(),
}));

vi.mock("@/v2/composables/useUnloadGuard", () => ({
  useUnloadGuard: vi.fn(),
}));

const GameCoverStub = defineComponent({
  setup(_, { expose }) {
    expose({ playLoad: () => 0 });
    return () => null;
  },
});

function save(
  id: number,
  file_name: string,
  overrides: Partial<SaveSchema> = {},
): SaveSchema {
  return {
    id,
    file_name,
    emulator: "retroarch",
    rom_id: 3,
    user_id: 1,
    created_at: `2026-09-14T0${id}:00:00`,
    updated_at: `2026-09-14T0${id}:00:00`,
    ...overrides,
  } as SaveSchema;
}

// Newest first, the order the launch screen sorts into.
const ARCHIVES = [
  save(3, "Pool [retroarch 2026-09-14 01-20-28].saves.zip"),
  save(2, "Pool [retroarch 2026-09-14 00-50-28].saves.zip"),
  save(1, "Pool [retroarch 2026-09-14 00-20-28].saves.zip"),
];

function romWith(saves: SaveSchema[]): DetailedRom {
  return {
    id: 3,
    name: "Archer Maclean's 3D Pool (USA)",
    platform_slug: "gba",
    platform_name: "Game Boy Advance",
    platform_display_name: "Game Boy Advance",
    fs_name: "Archer Maclean's 3D Pool (USA).gba",
    files: [],
    user_saves: saves,
    all_user_states: [],
    user_screenshots: [],
    metadatum: {},
  } as unknown as DetailedRom;
}

async function launch(opts: {
  picker: boolean;
  saves?: SaveSchema[];
}): Promise<VueWrapper> {
  mocks.container = {
    name: "WEBSTATION-DEV",
    emulator: "retroarch",
    protocol: "webstation",
    supports_save_picker: opts.picker,
    supports_memory_cards: false,
    supports_multiplayer: false,
  };
  mocks.getRom.mockResolvedValue({ data: romWith(opts.saves ?? ARCHIVES) });
  const wrapper = mount(Stream, {
    shallow: true,
    global: {
      renderStubDefaultSlot: true,
      // The launch flourish calls into the cover before the claim, so this
      // one stub has to answer rather than be inert.
      stubs: { GameCover: GameCoverStub },
    },
  });
  await flushPromises();
  return wrapper;
}

function preview(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents(AssetPreview)
    .find((p) => p.props("type") === "save");
}

function saveList(wrapper: VueWrapper) {
  return wrapper
    .findAllComponents(AssetList)
    .find((s) => s.props("type") === "save");
}

describe("Stream save picker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.claimSession.mockResolvedValue({ container: "WEBSTATION-DEV" });
  });

  it("offers every archive, newest already picked", async () => {
    const wrapper = await launch({ picker: true });

    const list = saveList(wrapper);
    expect(list).toBeDefined();
    expect((list!.props("assets") as SaveSchema[]).map((s) => s.id)).toEqual([
      3, 2, 1,
    ]);
    expect(list!.props("selectedId")).toBe(3);
    expect((preview(wrapper)!.props("asset") as SaveSchema).id).toBe(3);
  });

  it("dates the rows by the timestamp it sorted them on", async () => {
    // A content-hash rewrite moves updated_at without touching the save, so
    // showing it would date the second row "now" in a newest-first list.
    const wrapper = await launch({
      picker: true,
      saves: [
        save(1, "Pool [retroarch a].saves.zip", {
          updated_at: "2026-09-15T12:00:00",
        }),
        ...ARCHIVES.slice(0, 2),
      ],
    });

    expect((saveList(wrapper)!.props("assets") as SaveSchema[])[0].id).toBe(3);
    expect(saveList(wrapper)!.props("timestamp")).toBe("created");
    expect(preview(wrapper)!.props("timestamp")).toBe("created");
  });

  it("has no clear button: the claim always restores something", async () => {
    const wrapper = await launch({ picker: true });

    expect(preview(wrapper)!.props("clearable")).toBe(false);
  });

  it("keeps an older pick and sends it on the claim", async () => {
    const wrapper = await launch({ picker: true });

    await saveList(wrapper)!.vm.$emit("select", ARCHIVES[2]);
    expect(saveList(wrapper)!.props("selectedId")).toBe(1);
    expect((preview(wrapper)!.props("asset") as SaveSchema).id).toBe(1);

    await (wrapper.vm as unknown as { onPlay: () => Promise<void> }).onPlay();
    expect(mocks.claimSession.mock.calls[0][2]).toBe(1);
  });

  it("leaves bare save files out of the picker", async () => {
    const wrapper = await launch({
      picker: true,
      saves: [save(9, "Pool.srm"), ...ARCHIVES],
    });

    expect(
      (saveList(wrapper)!.props("assets") as SaveSchema[]).map((s) => s.id),
    ).toEqual([3, 2, 1]);
    expect(saveList(wrapper)!.props("selectedId")).toBe(3);
  });

  it("leaves another emulator's archives out of the picker", async () => {
    const wrapper = await launch({
      picker: true,
      saves: [
        save(9, "Pool [pcsx2 a].saves.zip", { emulator: "pcsx2" }),
        ...ARCHIVES,
      ],
    });

    expect(
      (saveList(wrapper)!.props("assets") as SaveSchema[]).map((s) => s.id),
    ).toEqual([3, 2, 1]);
  });

  it("reports instead of offering where the emulator keeps its save tree", async () => {
    const wrapper = await launch({ picker: false });

    expect(saveList(wrapper)).toBeUndefined();
    expect(wrapper.findComponent(SaveDataPanel).exists()).toBe(true);
  });

  it("reports no archive where this emulator only wrote bare files", async () => {
    // An EmulatorJS save under the same emulator name: the broker restores
    // archives only, so naming it would promise a restore that never happens.
    const wrapper = await launch({
      picker: false,
      saves: [save(9, "Pool.srm")],
    });

    expect(wrapper.findComponent(SaveDataPanel).props("save")).toBeNull();
  });

  it("sends no pick where the container would not honour one", async () => {
    const wrapper = await launch({ picker: false });

    await (wrapper.vm as unknown as { onPlay: () => Promise<void> }).onPlay();
    expect(mocks.claimSession.mock.calls[0][2]).toBeUndefined();
  });

  it("falls back to the newest when the picked archive is gone", async () => {
    const wrapper = await launch({ picker: true });
    const vm = wrapper.vm as unknown as { rom: unknown };

    await saveList(wrapper)!.vm.$emit("select", ARCHIVES[2]);
    expect(saveList(wrapper)!.props("selectedId")).toBe(1);

    // A rom refresh that no longer carries the archive the pick named.
    vm.rom = romWith(ARCHIVES.slice(0, 2));
    await flushPromises();

    expect(saveList(wrapper)!.props("selectedId")).toBe(3);
  });
});
