import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import UserProfile from "./UserProfile.vue";

vi.mock("vue-i18n");
vi.mock("@/services/api/user", () => ({ default: { updateUser: vi.fn() } }));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RBtn = {
  props: { prependIcon: { type: String, default: "" } },
  emits: ["click"],
  template: `<button type="button" :data-icon="prependIcon" @click="$emit('click')"><slot /></button>`,
};

const saved = userFixture({
  id: 1,
  avatar_path: "users/1/avatar.png",
  updated_at: "2026-01-01",
});

function mountProfile() {
  return mount(UserProfile, {
    global: {
      stubs: {
        RBtn,
        RIcon: true,
        RTag: true,
        RTextField: true,
        RSkeletonBlock: true,
        SettingsSection: { template: "<section><slot /></section>" },
        RetroAchievementsSection: true,
        ChangePasswordDialog: true,
      },
    },
  });
}

async function pick(wrapper: ReturnType<typeof mountProfile>) {
  await flushPromises();
  const input = wrapper.get<HTMLInputElement>("input[type='file']");
  Object.defineProperty(input.element, "files", {
    value: [new File(["a"], "a.png")],
    configurable: true,
  });
  await input.trigger("change");
}

describe("UserProfile avatar preview", () => {
  let urls = 0;

  beforeEach(() => {
    urls = 0;
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:${++urls}`);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    storeAuth().setCurrentUser(saved);
  });

  it("previews the picked file until the saved avatar replaces it", async () => {
    vi.mocked(userApi.updateUser).mockResolvedValue({
      data: { ...saved, updated_at: "2026-02-02" },
    } as never);
    const wrapper = mountProfile();
    const avatar = () => wrapper.get("img").attributes("src");

    await pick(wrapper);
    expect(avatar()).toBe("blob:1");

    await wrapper.get("[data-icon='mdi-check']").trigger("click");
    await flushPromises();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
    expect(avatar()).toBe("/api/users/1/avatar?ts=2026-02-02");
  });

  it("revokes the preview on unmount", async () => {
    const wrapper = mountProfile();
    await pick(wrapper);

    wrapper.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });
});
