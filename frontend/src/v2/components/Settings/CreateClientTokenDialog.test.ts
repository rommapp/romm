import { flushPromises, mount } from "@vue/test-utils";
import mitt from "mitt";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ClientTokenSchema } from "@/__generated__";
import type { Events } from "@/types/emitter";
import CreateClientTokenDialog from "./CreateClientTokenDialog.vue";

const { regenerateToken, pairToken, pollPairStatus, success } = vi.hoisted(
  () => ({
    regenerateToken: vi.fn(),
    pairToken: vi.fn(),
    pollPairStatus: vi.fn(),
    success: vi.fn(),
  }),
);

vi.mock("vue-i18n");

vi.mock("@/services/api/client-token", () => ({
  default: { regenerateToken, pairToken, pollPairStatus },
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error: vi.fn() }),
}));

vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ copy: vi.fn() }),
}));

const token = {
  id: 5,
  name: "Deck",
  scopes: [],
} as unknown as ClientTokenSchema;

async function openPairing(expiresIn: number) {
  pairToken.mockResolvedValue({
    data: { code: "ABC123", expires_in: expiresIn },
  });
  const emitter = mitt<Events>();
  const wrapper = mount(CreateClientTokenDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: ["modelValue"],
          template:
            '<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>',
        },
        RBtn: {
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RCheckbox: true,
        RIcon: true,
        RProgressCircular: true,
        RSelect: true,
        RTextField: true,
      },
    },
  });
  emitter.emit("showRegenerateClientTokenDialog", token);
  await flushPromises();
  const pair = wrapper
    .findAll("button")
    .find((b) => b.text() === "settings.pair-device");
  await pair!.trigger("click");
  await flushPromises();
  return { wrapper, emitter };
}

function counter(wrapper: Awaited<ReturnType<typeof openPairing>>["wrapper"]) {
  return wrapper.find(".r-v2-tok-dialog__pair-counter");
}

describe("CreateClientTokenDialog pairing", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    regenerateToken.mockResolvedValue({ data: { id: 5, raw_token: "rmm_x" } });
    pollPairStatus.mockResolvedValue({ data: {} });
  });

  afterEach(() => vi.useRealTimers());

  it("counts down, polling every third second, then expires", async () => {
    const { wrapper } = await openPairing(6);
    expect(counter(wrapper).text()).toBe("6s");

    await vi.advanceTimersByTimeAsync(1000);
    expect(counter(wrapper).text()).toBe("5s");
    expect(pollPairStatus).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(2000);
    expect(pollPairStatus).toHaveBeenCalledExactlyOnceWith("ABC123");

    await vi.advanceTimersByTimeAsync(3000);
    expect(pollPairStatus).toHaveBeenCalledOnce();
    expect(counter(wrapper).exists()).toBe(false);
    expect(wrapper.text()).toContain("settings.client-token-pair-expired");
  });

  // The poll answers 4xx once the device has claimed the code.
  it("reports the claim and stops when the poll is refused", async () => {
    pollPairStatus.mockRejectedValue(new Error("gone"));
    const { wrapper } = await openPairing(9);

    await vi.advanceTimersByTimeAsync(3000);
    expect(success).toHaveBeenCalledWith(
      "settings.client-token-pair-claimed",
      expect.anything(),
    );

    await vi.advanceTimersByTimeAsync(6000);
    expect(pollPairStatus).toHaveBeenCalledOnce();
    expect(wrapper.text()).not.toContain("settings.client-token-pair-expired");
  });

  it("stops polling once the dialog closes", async () => {
    const { wrapper } = await openPairing(9);

    const close = wrapper
      .findAll("button")
      .find((b) => b.text() === "common.close");
    await close!.trigger("click");
    await vi.advanceTimersByTimeAsync(9000);

    expect(pollPairStatus).not.toHaveBeenCalled();
  });
});
