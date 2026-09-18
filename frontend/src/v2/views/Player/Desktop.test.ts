import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { AxiosError } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import Desktop from "./Desktop.vue";

const mocks = vi.hoisted(() => ({
  claimDesktop: vi.fn(),
  releaseSession: vi.fn(),
  releaseSessionKeepalive: vi.fn(),
  heartbeatSession: vi.fn(),
  heartbeatTick: null as (() => Promise<void>) | null,
  routeLeave: null as (() => Promise<boolean> | boolean) | null,
  socketHandlers: {} as Record<string, (payload: unknown) => unknown>,
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: (guard: () => Promise<boolean>) => {
    mocks.routeLeave = guard;
  },
  useRoute: () => ({ query: { container: "WEBSTATION-DEV" } }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@vueuse/core", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@vueuse/core")>()),
  // The beat is driven by hand; the pagehide listener stays real.
  useIntervalFn: (tick: () => Promise<void>) => {
    mocks.heartbeatTick = tick;
  },
}));

vi.mock("@/plugins/router", () => ({
  ROUTES: { ADMINISTRATION: "administration" },
}));

vi.mock("@/services/api/streaming", () => ({
  default: {
    claimDesktop: mocks.claimDesktop,
    releaseSession: mocks.releaseSession,
    releaseSessionKeepalive: mocks.releaseSessionKeepalive,
  },
}));

vi.mock("@/stores/streaming", () => ({
  useStreamingStore: () => ({ heartbeatSession: mocks.heartbeatSession }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => () => Promise.resolve(true),
}));

vi.mock("@/v2/composables/usePageTitle", () => ({ usePageTitle: vi.fn() }));

vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: (event: string, handler: (payload: unknown) => unknown) => {
    mocks.socketHandlers[event] = handler;
  },
}));

const StreamStageStub = defineComponent({
  setup(_, { expose }) {
    expose({
      leaveFullscreen: () => Promise.resolve(),
      focusStream: () => {},
    });
    return () => null;
  },
});

type DesktopVm = { state: string; errorMessage: string };

// The view listens on window, so a mount left standing would answer the next
// test's pagehide too.
let mounted: VueWrapper | null = null;

const CLAIMED_AT = "2026-09-17T10:00:00";

async function openDesktop(): Promise<VueWrapper> {
  mocks.claimDesktop.mockResolvedValue({
    data: {
      host: "http://webstation-dev:8080",
      label: "PS2",
      platform: "ps2",
      claimed_at: CLAIMED_AT,
    },
  });
  mounted = mount(Desktop, {
    shallow: true,
    global: { stubs: { StreamStage: StreamStageStub } },
  });
  await flushPromises();
  return mounted;
}

async function refuseDesktop(detail: unknown): Promise<VueWrapper> {
  mocks.claimDesktop.mockRejectedValue(
    Object.assign(new AxiosError("HTTP 409"), {
      response: { status: 409, data: { detail } },
    }),
  );
  mounted = mount(Desktop, {
    shallow: true,
    global: { stubs: { StreamStage: StreamStageStub } },
  });
  await flushPromises();
  return mounted;
}

function vmOf(wrapper: VueWrapper): DesktopVm {
  return wrapper.vm as unknown as DesktopVm;
}

function endSession(notice: Record<string, unknown>): void {
  const handler = mocks.socketHandlers["streaming:session-ended"];
  expect(handler).toBeTypeOf("function");
  handler({ ended_by: "admin", reason: null, desktop: true, ...notice });
}

describe("Desktop session-ended notices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    mounted?.unmount();
    mounted = null;
  });

  it("ends the desktop when the notice names its container", async () => {
    const wrapper = await openDesktop();
    expect(vmOf(wrapper).state).toBe("running");

    endSession({ platform: "ps2", container: "WEBSTATION-DEV" });
    await flushPromises();

    expect(vmOf(wrapper).state).toBe("error");
    expect(vmOf(wrapper).errorMessage).toBe("play.session-ended-by");
  });

  it("holds the claim when the notice names another container", async () => {
    const wrapper = await openDesktop();

    endSession({ platform: "ps2", container: "WEBSTATION-OTHER" });
    await flushPromises();

    expect(vmOf(wrapper).state).toBe("running");
  });

  it("releases nothing once a notice has ended the claim", async () => {
    // The claim is gone, so an exit must not hand back whoever holds the
    // container next.
    await openDesktop();

    endSession({ platform: "ps2", container: "WEBSTATION-DEV" });
    await flushPromises();
    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.releaseSessionKeepalive).not.toHaveBeenCalled();
    expect(mocks.releaseSession).not.toHaveBeenCalled();
  });
});

describe("Desktop heartbeats", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    mounted?.unmount();
    mounted = null;
  });

  it("beats for the claim it made", async () => {
    // Unstamped, the beat keeps alive whatever this admin runs on the
    // container, such as a game that swept a stale desktop off it.
    const wrapper = await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({ status: "active" });

    await mocks.heartbeatTick?.();

    expect(mocks.heartbeatSession).toHaveBeenCalledWith(
      "ps2",
      "WEBSTATION-DEV",
      CLAIMED_AT,
    );
    expect(vmOf(wrapper).state).toBe("running");
  });

  it("drops the claim when the beat reports the session ended", async () => {
    const wrapper = await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({
      status: "ended",
      termination: { ended_by: "admin" },
    });

    await mocks.heartbeatTick?.();
    window.dispatchEvent(new Event("pagehide"));

    expect(vmOf(wrapper).state).toBe("error");
    expect(vmOf(wrapper).errorMessage).toBe("play.session-ended-by");
    expect(mocks.releaseSessionKeepalive).not.toHaveBeenCalled();
  });

  it("leaves the view without a release once the beat ended the claim", async () => {
    await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({ status: "ended" });

    await mocks.heartbeatTick?.();

    expect(await mocks.routeLeave?.()).toBe(true);
    expect(mocks.releaseSession).not.toHaveBeenCalled();
  });
});

describe("Desktop releases", () => {
  // Unstamped, a release reaches whichever session took the container.
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    mounted?.unmount();
    mounted = null;
  });

  it("names the claim it releases on exit", async () => {
    mocks.releaseSession.mockResolvedValue({});
    await openDesktop();

    expect(await mocks.routeLeave?.()).toBe(true);

    expect(mocks.releaseSession).toHaveBeenCalledWith(
      "ps2",
      undefined,
      "WEBSTATION-DEV",
      undefined,
      CLAIMED_AT,
    );
  });

  it("names the claim it releases when the tab closes", async () => {
    await openDesktop();

    window.dispatchEvent(new Event("pagehide"));

    expect(mocks.releaseSessionKeepalive).toHaveBeenCalledWith(
      "ps2",
      "WEBSTATION-DEV",
      CLAIMED_AT,
    );
  });
});

describe("Desktop refused claims", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    mounted?.unmount();
    mounted = null;
  });

  it("names the game holding the container", async () => {
    const wrapper = await refuseDesktop({
      rom_name: "Ico",
      claimed_at: "2026-09-17T10:00:00",
      draining: false,
    });

    expect(vmOf(wrapper).errorMessage).toBe("play.desktop-error-occupied");
  });

  it("says to come back when the container is still saving", async () => {
    const wrapper = await refuseDesktop({
      rom_name: null,
      claimed_at: null,
      draining: true,
    });

    expect(vmOf(wrapper).errorMessage).toBe("play.stream-occupied-draining");
  });
});
