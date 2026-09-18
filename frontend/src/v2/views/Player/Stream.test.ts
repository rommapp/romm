import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  fetchSessionStatus: vi.fn(),
  heartbeatSession: vi.fn(),
  joinSession: vi.fn(),
  releaseSession: vi.fn(),
  releaseSessionKeepalive: vi.fn(),
  saveAndExit: vi.fn(),
  saveAndExitKeepalive: vi.fn(),
  container: null as Record<string, unknown> | null,
  presenceTick: null as (() => Promise<void>) | null,
  socketHandlers: {} as Record<string, (payload: unknown) => unknown>,
  query: {} as Record<string, string>,
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
  useRoute: () => ({ params: { rom: "3" }, query: mocks.query }),
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
    fetchSessionStatus: mocks.fetchSessionStatus,
    forgetJoinableSession: vi.fn(),
    heartbeatSession: mocks.heartbeatSession,
    joinSession: mocks.joinSession,
    releaseSession: mocks.releaseSession,
    releaseSessionKeepalive: mocks.releaseSessionKeepalive,
    saveAndExit: mocks.saveAndExit,
    saveAndExitKeepalive: mocks.saveAndExitKeepalive,
  }),
}));

vi.mock("@/v2/composables/useActivityPresence", () => ({
  useActivityPresence: (_rom: unknown, tick: () => Promise<void>) => {
    mocks.presenceTick = tick;
    return {
      start: vi.fn(),
      stopHeartbeat: vi.fn(),
      emitStop: vi.fn(),
      stop: vi.fn(),
    };
  },
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
  useSocketEvent: (event: string, handler: (payload: unknown) => unknown) => {
    mocks.socketHandlers[event] = handler;
  },
}));

vi.mock("@/v2/composables/useStageActive", () => ({
  useStageActive: vi.fn(),
}));

vi.mock("@/v2/composables/useUnloadGuard", () => ({
  useUnloadGuard: vi.fn(),
}));

/** Renders nothing and answers the methods the view calls on the real child. */
function exposingStub(api: Record<string, unknown>) {
  return defineComponent({
    setup(_, { expose }) {
      expose(api);
      return () => null;
    },
  });
}

// The stage owns fullscreen, which the ended path leaves before anything else.
const StreamStageStub = exposingStub({
  enterFullscreen: () => Promise.resolve(),
  leaveFullscreen: () => Promise.resolve(),
  focusStream: () => {},
});

const GameCoverStub = exposingStub({ playLoad: () => 0 });

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

// The view listens on document and window, so a mount left standing would
// answer the next test's visibilitychange and pagehide too.
const mounted: VueWrapper[] = [];

afterEach(() => {
  for (const wrapper of mounted.splice(0)) {
    if (wrapper.exists()) wrapper.unmount();
  }
});

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
      stubs: { GameCover: GameCoverStub, StreamStage: StreamStageStub },
    },
  });
  mounted.push(wrapper);
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

const CLAIM = {
  container: "WEBSTATION-DEV",
  claimed_at: "2026-09-17T10:00:00",
};

describe("Stream save picker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.claimSession.mockResolvedValue(CLAIM);
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

type StreamVm = {
  onPlay: () => Promise<void>;
  playerState: string;
  endedDialogOpen: boolean;
  holdsClaim: boolean;
  containerHost: string;
};

function vmOf(wrapper: VueWrapper): StreamVm {
  return wrapper.vm as unknown as StreamVm;
}

function endSession(notice: Record<string, unknown>): void {
  const handler = mocks.socketHandlers["streaming:session-ended"];
  expect(handler).toBeTypeOf("function");
  handler({ ended_by: "admin", reason: null, ...notice });
}

async function launchReady(): Promise<void> {
  const handler = mocks.socketHandlers["streaming:launch-ready"];
  expect(handler).toBeTypeOf("function");
  await handler({
    platform: "gba",
    container: CLAIM.container,
    host: "http://webstation-dev:8080",
    resume: null,
  });
}

describe("Stream session-ended notices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.claimSession.mockResolvedValue(CLAIM);
  });

  it("ends the game when the notice names the container it claimed", async () => {
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();

    endSession({ platform: "gba", container: "WEBSTATION-DEV" });
    await flushPromises();

    expect(vmOf(wrapper).playerState).toBe("exited");
    expect(vmOf(wrapper).endedDialogOpen).toBe(true);
  });

  it("keeps playing when the notice names another container", async () => {
    // A pool serves one platform from several containers, so the player can
    // hold a second session the same room hears about.
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    await launchReady();
    expect(vmOf(wrapper).playerState).toBe("playing");

    endSession({ platform: "gba", container: "WEBSTATION-DEV-2" });
    await flushPromises();

    expect(vmOf(wrapper).playerState).toBe("playing");
    expect(vmOf(wrapper).endedDialogOpen).toBe(false);
  });

  it("keeps launching when an admin's own desktop ends", async () => {
    // The 202 has not landed, so the container is not known yet and the
    // desktop flag is all that tells the two claims apart.
    let claimed = (_: typeof CLAIM) => {};
    mocks.claimSession.mockReturnValue(
      new Promise<typeof CLAIM>((resolve) => {
        claimed = resolve;
      }),
    );
    const wrapper = await launch({ picker: false });
    const playing = vmOf(wrapper).onPlay();
    await flushPromises();

    endSession({
      platform: "gba",
      container: "WEBSTATION-DEV-2",
      desktop: true,
    });
    await flushPromises();

    expect(vmOf(wrapper).playerState).toBe("loading");
    claimed(CLAIM);
    await playing;
  });
});

describe("Stream claim hygiene", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.claimSession.mockResolvedValue(CLAIM);
    mocks.releaseSession.mockResolvedValue(true);
  });

  it("names the claim it holds when it releases", async () => {
    // An unnamed release reaches whatever the platform is running, which after
    // a takeover is somebody else's session.
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();

    wrapper.unmount();

    expect(mocks.releaseSession).toHaveBeenCalledWith(
      "gba",
      false,
      CLAIM.container,
      CLAIM.claimed_at,
    );
  });

  it("releases nothing on unmount once the session ended elsewhere", async () => {
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();

    endSession({ platform: "gba", container: CLAIM.container });
    await flushPromises();
    wrapper.unmount();

    expect(vmOf(wrapper).holdsClaim).toBe(false);
    expect(mocks.releaseSession).not.toHaveBeenCalled();
  });

  it("hands the container back once when the game comes up after the exit", async () => {
    const wrapper = await launch({ picker: false });
    const vm = vmOf(wrapper);
    await vm.onPlay();
    vm.playerState = "exited";

    await launchReady();
    await flushPromises();
    wrapper.unmount();

    expect(mocks.releaseSession).toHaveBeenCalledTimes(1);
    expect(mocks.releaseSession).toHaveBeenCalledWith(
      "gba",
      false,
      CLAIM.container,
      CLAIM.claimed_at,
    );
  });

  it("names the claim it saves when it leaves a running game", async () => {
    mocks.saveAndExit.mockResolvedValue({ released: true, saved: true });
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    await launchReady();

    wrapper.unmount();

    const [platform, , wait, container, claimedAt] =
      mocks.saveAndExit.mock.calls[0];
    expect([platform, wait, container, claimedAt]).toEqual([
      "gba",
      false,
      CLAIM.container,
      CLAIM.claimed_at,
    ]);
  });

  it("names the claim it saves when the tab closes on a running game", async () => {
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    await launchReady();

    window.dispatchEvent(new Event("pagehide"));

    const [platform, , container, claimedAt] =
      mocks.saveAndExitKeepalive.mock.calls[0];
    expect([platform, container, claimedAt]).toEqual([
      "gba",
      CLAIM.container,
      CLAIM.claimed_at,
    ]);
    wrapper.unmount();
  });

  it("names the claim it saves on Save & Exit", async () => {
    mocks.saveAndExit.mockResolvedValue({ released: true, saved: true });
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    await launchReady();

    await (
      wrapper.vm as unknown as { performSaveAndExit: () => Promise<void> }
    ).performSaveAndExit();

    const [platform, , wait, container, claimedAt] =
      mocks.saveAndExit.mock.calls[0];
    expect([platform, wait, container, claimedAt]).toEqual([
      "gba",
      true,
      CLAIM.container,
      CLAIM.claimed_at,
    ]);
    wrapper.unmount();
  });

  it("names the claim on the heartbeat", async () => {
    // The heartbeat restamps whatever the platform is running otherwise, which
    // keeps another player's session alive and lets this one go stale.
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    mocks.heartbeatSession.mockResolvedValue(null);

    await mocks.presenceTick?.();

    expect(mocks.heartbeatSession).toHaveBeenCalledWith(
      "gba",
      CLAIM.container,
      CLAIM.claimed_at,
    );
    wrapper.unmount();
  });
});

// The heartbeat only runs once the game is on screen, so while loading the
// status poll is what can find it; a tab coming back to the front runs one.
async function pollStatus(): Promise<void> {
  document.dispatchEvent(new Event("visibilitychange"));
  await flushPromises();
}

describe("Stream launch recovery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.claimSession.mockResolvedValue(CLAIM);
  });

  it("enters the stream when the poll finds the game already up", async () => {
    // launch-ready is pushed once, so a socket that dropped during the launch
    // left the tab loading over a game that was running.
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    mocks.fetchSessionStatus.mockResolvedValue({
      status: "active",
      platform: "gba",
      host: "http://webstation-dev:8080/room/x",
      container: CLAIM.container,
    });

    await pollStatus();

    // With one container per platform a re-claim lands on the same container,
    // so only the stamp keeps the poll from answering with another tab's claim.
    expect(mocks.fetchSessionStatus).toHaveBeenCalledExactlyOnceWith(
      "gba",
      CLAIM.claimed_at,
    );
    expect(vmOf(wrapper).playerState).toBe("playing");
    expect(vmOf(wrapper).containerHost).toBe(
      "http://webstation-dev:8080/room/x",
    );
    wrapper.unmount();
  });

  it("keeps waiting when the poll finds a game on another container", async () => {
    // The unnamed poll reports any session the player holds on the platform,
    // which can be another tab's.
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    mocks.fetchSessionStatus.mockResolvedValue({
      status: "active",
      platform: "gba",
      host: "http://webstation-dev-2:8080/room/y",
      container: "WEBSTATION-DEV-2",
    });

    await pollStatus();

    expect(vmOf(wrapper).playerState).toBe("loading");
    expect(vmOf(wrapper).containerHost).toBe("");
    wrapper.unmount();
  });

  it("keeps waiting while the launch has no room yet", async () => {
    const wrapper = await launch({ picker: false });
    await vmOf(wrapper).onPlay();
    mocks.fetchSessionStatus.mockResolvedValue({
      status: "active",
      platform: "gba",
      host: null,
      container: CLAIM.container,
    });

    await pollStatus();

    expect(vmOf(wrapper).playerState).toBe("loading");
    wrapper.unmount();
  });
});

describe("Stream join", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.joinSession.mockResolvedValue({ host: "http://box:3000/room/x" });
    mocks.query = { join: "1", container: "http://box:8000" };
  });

  afterEach(() => {
    mocks.query = {};
  });

  it("joins the session on the container the game page named", async () => {
    // A pool has several sessions on one platform, so without the container
    // the join lands on whichever the backend walks to first.
    const wrapper = await launch({ picker: false });
    await flushPromises();

    expect(mocks.joinSession).toHaveBeenCalledWith("gba", "http://box:8000");
    expect(vmOf(wrapper).playerState).toBe("playing");
    wrapper.unmount();
  });

  it("joins without one when the page had no container to name", async () => {
    mocks.query = { join: "1" };
    const wrapper = await launch({ picker: false });
    await flushPromises();

    expect(mocks.joinSession).toHaveBeenCalledWith("gba", undefined);
    wrapper.unmount();
  });
});
