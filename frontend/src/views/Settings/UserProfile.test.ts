import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PasswordField from "@/components/shared/PasswordField.vue";
import { RTextField } from "@/lib";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import UserProfile from "./UserProfile.vue";

vi.mock("vue-i18n");
vi.mock("@/services/api/user", () => ({ default: { updateUser: vi.fn() } }));
vi.mock("@/composables/useSnackbar", () => ({
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

describe("UserProfile email change", () => {
  async function changeEmail(wrapper: ReturnType<typeof mountProfile>) {
    await flushPromises();
    const email = wrapper
      .findAllComponents(RTextField)
      .find((f) => f.attributes("type") === "email");
    email?.vm.$emit("update:modelValue", "new@example.com");
    await flushPromises();
  }

  const apply = (wrapper: ReturnType<typeof mountProfile>) =>
    wrapper.get("[data-icon='mdi-check']");

  it("asks for the current password before saving a new email", async () => {
    storeAuth().setCurrentUser(saved);
    vi.mocked(userApi.updateUser).mockResolvedValue({ data: saved } as never);
    const wrapper = mountProfile();

    await changeEmail(wrapper);
    expect(apply(wrapper).attributes()).toHaveProperty("disabled");

    wrapper
      .getComponent(PasswordField)
      .vm.$emit("update:modelValue", "test_admin_password");
    await flushPromises();
    await apply(wrapper).trigger("click");
    await flushPromises();

    expect(userApi.updateUser).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        email: "new@example.com",
        current_password: "test_admin_password",
      }),
    );
  });

  it("asks for the current password before saving a new username", async () => {
    storeAuth().setCurrentUser(saved);
    const wrapper = mountProfile();
    await flushPromises();

    wrapper
      .findAllComponents(RTextField)
      .find((f) => f.attributes("type") !== "email")
      ?.vm.$emit("update:modelValue", "renamed");
    await flushPromises();

    expect(wrapper.findComponent(PasswordField).exists()).toBe(true);
    expect(apply(wrapper).attributes()).toHaveProperty("disabled");
  });

  it("locks the email when the identity provider manages it", async () => {
    storeAuth().setCurrentUser({ ...saved, email_managed_by_oidc: true });
    const wrapper = mountProfile();
    await flushPromises();

    const email = wrapper
      .findAllComponents(RTextField)
      .find((f) => f.attributes("type") === "email");
    expect(email?.props("readonly")).toBe(true);
  });

  it("saves a new email without it on an account with no password", async () => {
    storeAuth().setCurrentUser({ ...saved, has_password: false });
    const wrapper = mountProfile();

    await changeEmail(wrapper);

    expect(wrapper.findComponent(PasswordField).exists()).toBe(false);
    expect(apply(wrapper).attributes()).not.toHaveProperty("disabled");
  });
});
