import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DevicePair from "./DevicePair.vue";

const { getPending, approve } = vi.hoisted(() => ({
  getPending: vi.fn(),
  approve: vi.fn(),
}));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: { user_code: "ABCD-1234" } }),
}));

vi.mock("@/services/api/device-auth", () => ({
  default: { getPending, approve, deny: vi.fn() },
}));

async function mountApproved() {
  const wrapper = mount(DevicePair, {
    global: {
      stubs: {
        RBtn: {
          emits: ["click"],
          template: "<button @click=\"$emit('click')\"><slot /></button>",
        },
        RChip: true,
        RIcon: true,
        RSelect: true,
        RSpinner: true,
        RTextField: true,
      },
    },
  });
  await flushPromises();
  await wrapper.findAll("button")[1]!.trigger("click");
  await flushPromises();
  return wrapper;
}

describe("DevicePair auto-close", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
    vi.spyOn(window, "close").mockImplementation(() => undefined);
    getPending.mockResolvedValue({
      data: {
        client_device_identifier: "dev-1",
        name: "Steam Deck",
        client: "argosy",
        platform: null,
        client_version: null,
        requested_scopes: ["roms.read"],
        allowed_scopes: ["roms.read"],
        expires_at: "2030-01-01T00:00:00Z",
      },
    });
    approve.mockResolvedValue({ data: {} });
  });

  it("counts down and closes the window once approved", async () => {
    const wrapper = await mountApproved();
    expect(approve).toHaveBeenCalledOnce();
    expect(wrapper.find(".r-v2-devpair__hint").exists()).toBe(true);

    await vi.advanceTimersByTimeAsync(2000);
    expect(window.close).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1000);
    expect(window.close).toHaveBeenCalledOnce();
    expect(wrapper.find(".r-v2-devpair__hint").exists()).toBe(false);
  });

  it("stops counting once unmounted", async () => {
    const wrapper = await mountApproved();

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(3000);

    expect(window.close).not.toHaveBeenCalled();
  });
});
