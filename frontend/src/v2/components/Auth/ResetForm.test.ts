import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeHeartbeat from "@/stores/heartbeat";
import ResetForm from "./ResetForm.vue";

const { requestPasswordReset, success } = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
  success: vi.fn(),
}));

vi.mock("@/services/api/identity", () => ({
  default: { requestPasswordReset },
}));
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/v2/composables/useSnackbar", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/v2/composables/useSnackbar")>()),
  useSnackbar: () => ({ success, error: vi.fn() }),
}));

async function requestFor(username: string) {
  const wrapper = mount(ResetForm);
  await wrapper.find("input").setValue(username);
  await wrapper.find("form").trigger("submit");
  await flushPromises();
  return wrapper;
}

describe("ResetForm", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    requestPasswordReset.mockResolvedValue({});
  });

  it("says the link is on its way when the server sends email", async () => {
    storeHeartbeat().value.NOTIFICATIONS.EMAIL_ENABLED = true;

    const wrapper = await requestFor("player");

    expect(requestPasswordReset).toHaveBeenCalledWith("player");
    expect(success.mock.calls[0][0]).toBe("login.reset-sent-email");
    expect(wrapper.emitted("done")).toHaveLength(1);
  });

  it("points to the admin when it doesn't", async () => {
    storeHeartbeat().value.NOTIFICATIONS.EMAIL_ENABLED = false;

    await requestFor("player");

    expect(success.mock.calls[0][0]).toBe("login.reset-sent");
  });
});
