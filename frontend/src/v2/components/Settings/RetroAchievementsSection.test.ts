import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import RetroAchievementsSection from "./RetroAchievementsSection.vue";

const { updateUser, refreshRetroAchievements, success, error, confirm } =
  vi.hoisted(() => ({
    updateUser: vi.fn(),
    refreshRetroAchievements: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    confirm: vi.fn(),
  }));

vi.mock("@/services/api/user", () => ({
  default: { updateUser, refreshRetroAchievements },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({ useConfirm: () => confirm }));

const RBtnStub = {
  name: "RBtn",
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    prependIcon: { type: String, default: "" },
  },
  emits: ["click"],
  template:
    "<button :disabled='disabled' @click=\"$emit('click')\"><slot /></button>",
};

const RTextFieldStub = {
  name: "RTextField",
  props: { modelValue: { type: String, default: "" } },
  emits: ["update:modelValue"],
  template:
    "<input :value='modelValue' @input=\"$emit('update:modelValue', $event.target.value)\" />",
};

function user(raUsername: string | null) {
  return userFixture({ id: 7, ra_username: raUsername });
}

function mountSection(raUsername: string | null) {
  storeAuth().setCurrentUser(user(raUsername));
  return mount(RetroAchievementsSection, {
    global: {
      stubs: {
        RBtn: RBtnStub,
        RTag: true,
        RTextField: RTextFieldStub,
        SettingsSection: { template: "<div><slot /></div>" },
      },
    },
  });
}

function unlinkButton(wrapper: ReturnType<typeof mountSection>) {
  return wrapper
    .findAllComponents(RBtnStub)
    .find((btn) => btn.props("prependIcon") === "mdi-link-variant-off");
}

beforeEach(() => {
  setActivePinia(createPinia());
  updateUser.mockReset();
  refreshRetroAchievements.mockReset();
  success.mockReset();
  error.mockReset();
  confirm.mockReset().mockResolvedValue(true);
});

describe("RetroAchievementsSection unlink", () => {
  it("is offered only while an account is linked", () => {
    expect(unlinkButton(mountSection(null))).toBeUndefined();
    expect(unlinkButton(mountSection("alice"))).toBeDefined();
  });

  it("clears the linked account and updates the current user", async () => {
    updateUser.mockResolvedValue({ data: user(null) });
    const wrapper = mountSection("alice");

    await unlinkButton(wrapper)!.trigger("click");
    await flushPromises();

    expect(updateUser).toHaveBeenCalledWith({
      id: 7,
      clear_ra_username: true,
    });
    expect(storeAuth().user?.ra_username).toBeNull();
    expect(success).toHaveBeenCalledWith("settings.ra-unlinked", {
      icon: "mdi-check-bold",
    });
    expect(confirm).toHaveBeenCalledWith(
      expect.objectContaining({ tone: "danger" }),
    );
    expect(unlinkButton(wrapper)).toBeUndefined();
  });

  it("keeps the account linked when the confirmation is cancelled", async () => {
    confirm.mockResolvedValue(false);
    const wrapper = mountSection("alice");

    await unlinkButton(wrapper)!.trigger("click");
    await flushPromises();

    expect(updateUser).not.toHaveBeenCalled();
    expect(storeAuth().user?.ra_username).toBe("alice");
  });

  it("keeps the account linked when the update fails", async () => {
    updateUser.mockRejectedValue(new Error("boom"));
    vi.spyOn(console, "error").mockImplementation(() => {});
    const wrapper = mountSection("alice");

    await unlinkButton(wrapper)!.trigger("click");
    await flushPromises();

    expect(storeAuth().user?.ra_username).toBe("alice");
    expect(error).toHaveBeenCalledWith("settings.ra-update-failed", {
      icon: "mdi-close-circle",
    });
  });
});

describe("RetroAchievementsSection save", () => {
  it("offers Unlink once a new username is saved", async () => {
    updateUser.mockResolvedValue({ data: user("alice") });
    refreshRetroAchievements.mockResolvedValue({});
    const wrapper = mountSection(null);

    await wrapper.find("input").setValue("alice");
    await wrapper.find("input").trigger("keyup", { key: "Enter" });
    await flushPromises();

    expect(updateUser).toHaveBeenCalledWith({ id: 7, ra_username: "alice" });
    expect(storeAuth().user?.ra_username).toBe("alice");
    expect(unlinkButton(wrapper)).toBeDefined();
  });

  it("ignores Enter on an empty field", async () => {
    const wrapper = mountSection("alice");

    await wrapper.find("input").setValue("  ");
    await wrapper.find("input").trigger("keyup", { key: "Enter" });
    await flushPromises();

    expect(updateUser).not.toHaveBeenCalled();
    expect(refreshRetroAchievements).not.toHaveBeenCalled();
  });
});
