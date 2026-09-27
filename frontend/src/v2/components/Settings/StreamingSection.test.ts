import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StreamingSection from "./StreamingSection.vue";

const { adminListContainers, releaseSession, confirm, push } = vi.hoisted(
  () => ({
    adminListContainers: vi.fn(),
    releaseSession: vi.fn(),
    confirm: vi.fn(),
    push: vi.fn(),
  }),
);

vi.mock("@/services/api/streaming", () => ({
  default: { adminListContainers, releaseSession },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}::${JSON.stringify(params)}` : key,
    locale: { value: "en_US" },
  }),
}));

vi.mock("vue-router", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/plugins/router", () => ({
  ROUTES: { STREAM_DESKTOP: "stream-desktop" },
}));

vi.mock("@/v2/composables/useConfirm", () => ({ useConfirm: () => confirm }));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RBtnStub = {
  name: "RBtn",
  props: ["disabled", "prependIcon"],
  template: "<button :disabled='disabled'><slot /></button>",
};

function container(overrides: Record<string, unknown> = {}) {
  return {
    container: "http://webstation:8000",
    name: "WEBSTATION-DEV",
    label: "Webstation",
    host: "https://webstation:8080",
    platforms: ["ps2"],
    supports_desktop: true,
    configured: true,
    draining: false,
    session: null,
    ...overrides,
  };
}

async function mountSection() {
  const wrapper = mount(StreamingSection, {
    global: {
      stubs: {
        RBtn: RBtnStub,
        RIcon: true,
        RSpinner: true,
      },
    },
  });
  await flushPromises();
  return wrapper;
}

function desktopButton(wrapper: Awaited<ReturnType<typeof mountSection>>) {
  return wrapper
    .findAllComponents(RBtnStub)
    .find((btn) => btn.props("prependIcon") === "mdi-desktop-classic");
}

describe("StreamingSection draining containers", () => {
  beforeEach(() => {
    confirm.mockReset();
    push.mockReset();
    releaseSession.mockReset();
    adminListContainers.mockReset();
    adminListContainers.mockResolvedValue({
      data: { enabled: true, containers: [container()] },
    });
  });

  it("calls a free container idle", async () => {
    const wrapper = await mountSection();

    expect(wrapper.find(".r-v2-streaming__state").text()).toBe(
      "settings.streaming-idle",
    );
    expect(desktopButton(wrapper)?.props("disabled")).toBe(false);
  });

  it("says a draining container is still shutting down its last session", async () => {
    adminListContainers.mockResolvedValue({
      data: { enabled: true, containers: [container({ draining: true })] },
    });

    const wrapper = await mountSection();

    expect(wrapper.find(".r-v2-streaming__state").text()).toBe(
      "settings.streaming-draining",
    );
  });

  it("holds the desktop shut until the drain finishes", async () => {
    adminListContainers.mockResolvedValue({
      data: { enabled: true, containers: [container({ draining: true })] },
    });

    const wrapper = await mountSection();

    expect(desktopButton(wrapper)?.props("disabled")).toBe(true);
  });
});

describe("StreamingSection desktop link", () => {
  beforeEach(() => {
    push.mockReset();
    adminListContainers.mockReset();
    adminListContainers.mockResolvedValue({
      data: { enabled: true, containers: [container()] },
    });
  });

  it("names the container by its name, not its broker host", async () => {
    const wrapper = await mountSection();

    await desktopButton(wrapper)?.trigger("click");

    expect(push).toHaveBeenCalledWith({
      name: "stream-desktop",
      query: { container: "WEBSTATION-DEV" },
    });
  });
});
