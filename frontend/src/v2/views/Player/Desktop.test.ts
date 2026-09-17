import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import Desktop from "./Desktop.vue";

const mocks = vi.hoisted(() => ({
  claimDesktop: vi.fn(),
  releaseSession: vi.fn(),
  releaseSessionKeepalive: vi.fn(),
  heartbeatSession: vi.fn(),
  socketHandlers: {} as Record<string, (payload: unknown) => unknown>,
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
  useRoute: () => ({ query: { container: "WEBSTATION-DEV" } }),
  useRouter: () => ({ push: vi.fn() }),
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
