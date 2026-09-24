import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
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

const StreamStageStub = defineComponent({
  props: { active: { type: Boolean, default: false } },
  setup(_, { expose }) {
    expose({
      leaveFullscreen: () => Promise.resolve(),
      focusStream: () => {},
    });
    return () => null;
  },
});

// The view listens on window, so a mount left standing would answer the next
// test's pagehide too.
let mounted: VueWrapper | null = null;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  mounted?.unmount();
  mounted = null;
});

async function openDesktop(): Promise<VueWrapper> {
  mocks.claimDesktop.mockResolvedValue({
    data: { host: "http://webstation-dev:8080", label: "PS2", platform: "ps2" },
  });
  mounted = mount(Desktop, {
    shallow: true,
    global: { stubs: { StreamStage: StreamStageStub } },
  });
  await flushPromises();
  return mounted;
}

function streamIsLive(wrapper: VueWrapper): boolean | undefined {
  return wrapper.findComponent(StreamStageStub).props("active");
}

describe("Desktop heartbeats", () => {
  it("beats for the container it claimed", async () => {
    // Unnamed, the beat only reaches the platform's first pool.
    const wrapper = await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({ status: "active" });

    await mocks.heartbeatTick?.();

    expect(mocks.heartbeatSession).toHaveBeenCalledWith(
      "ps2",
      "WEBSTATION-DEV",
    );
    expect(streamIsLive(wrapper)).toBe(true);
  });

  it("stops the stream when the beat reports the session ended", async () => {
    const wrapper = await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({ status: "ended" });

    await mocks.heartbeatTick?.();
    await flushPromises();

    expect(streamIsLive(wrapper)).toBe(false);
  });

  it("releases nothing once the beat ended the claim", async () => {
    // The claim is gone, so an exit must not hand back whoever holds the
    // container next.
    await openDesktop();
    mocks.heartbeatSession.mockResolvedValue({ status: "ended" });

    await mocks.heartbeatTick?.();
    window.dispatchEvent(new Event("pagehide"));

    expect(await mocks.routeLeave?.()).toBe(true);
    expect(mocks.releaseSessionKeepalive).not.toHaveBeenCalled();
    expect(mocks.releaseSession).not.toHaveBeenCalled();
  });
});
