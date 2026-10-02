import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";
import RetroAchievementsSection from "./RetroAchievementsSection.vue";

const { updateUser, refreshRetroAchievements, success, error } = vi.hoisted(
  () => ({
    updateUser: vi.fn(),
    refreshRetroAchievements: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
  }),
);

vi.mock("@/services/api/user", () => ({
  default: { updateUser, refreshRetroAchievements },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error }),
}));

const RBtnStub = {
  name: "RBtn",
  props: ["disabled", "loading", "prependIcon"],
  emits: ["click"],
  template:
    "<button :disabled='disabled' @click=\"$emit('click')\"><slot /></button>",
};

function user(raUsername: string | null): User {
  return { id: 7, ra_username: raUsername } as unknown as User;
}

function mountSection(raUsername: string | null) {
  storeAuth().setCurrentUser(user(raUsername));
  return mount(RetroAchievementsSection, {
    global: {
      stubs: {
        RBtn: RBtnStub,
        RTag: true,
        RTextField: true,
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

describe("RetroAchievementsSection unlink", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    updateUser.mockReset();
    success.mockReset();
    error.mockReset();
  });

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
    expect(unlinkButton(wrapper)).toBeUndefined();
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
