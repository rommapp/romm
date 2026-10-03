import { type VueWrapper, flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserPermissionsSchema } from "@/__generated__";
import type { Events } from "@/types/emitter";
import { userFixture } from "@/utils/user.fixtures";
import AgeLimitFields from "./AgeLimitFields.vue";
import EditUserDialog from "./EditUserDialog.vue";

const {
  fetchCatalog,
  fetchUserPermissions,
  getPlatforms,
  updateUserPermissions,
  updateUser,
} = vi.hoisted(() => ({
  fetchCatalog: vi.fn(),
  getPlatforms: vi.fn(),
  fetchUserPermissions: vi.fn(),
  updateUserPermissions: vi.fn(),
  updateUser: vi.fn(),
}));

vi.mock("vue-i18n");
vi.mock("@/services/api/permissions", () => ({
  default: {
    fetchUserPermissions,
    updateUserPermissions,
    fetchCatalog,
  },
}));
vi.mock("@/services/api/user", () => ({ default: { updateUser } }));
vi.mock("@/services/api/platform", () => ({
  default: { getPlatforms },
}));
vi.mock("@/stores/permissionGroups", () => ({
  default: () => ({ groups: [], ensureLoaded: () => Promise.resolve() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};

// The access section loads behind the avatar; leave it pending by default.
beforeEach(() => {
  vi.resetAllMocks();
  fetchUserPermissions.mockReturnValue(new Promise(() => undefined));
  fetchCatalog.mockReturnValue(new Promise(() => undefined));
  getPlatforms.mockReturnValue(new Promise(() => undefined));
});

function permissions(overrides: Partial<UserPermissionsSchema> = {}) {
  return {
    data: {
      user_id: 4,
      permission_group_id: 1,
      overrides: [],
      hidden: [],
      age_limit: null,
      hide_unrated_roms: null,
      ...overrides,
    },
  };
}

async function mountDialog(role: "admin" | "user" = "admin") {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(EditUserDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        RBtn: {
          emits: ["click"],
          template: `<button @click="$emit('click')"><slot /></button>`,
        },
        RIcon: true,
        RSelect: true,
        RSpinner: true,
        RSwitch: true,
        RTextField: true,
        HiddenGamesPicker: true,
        HiddenPlatformsPicker: true,
        OverridesMatrix: true,
        AgeLimitFields: true,
      },
    },
  });
  const open = (id = 4) => {
    emitter.emit("showEditUserDialog", userFixture({ id, role }));
    return flushPromises();
  };
  await open();
  return { wrapper, open };
}

async function pick(
  wrapper: Awaited<ReturnType<typeof mountDialog>>["wrapper"],
) {
  const input = wrapper.get<HTMLInputElement>("input[type='file']");
  Object.defineProperty(input.element, "files", {
    value: [new File(["a"], "a.png")],
    configurable: true,
  });
  await input.trigger("change");
}

describe("EditUserDialog avatar preview", () => {
  let urls = 0;

  beforeEach(() => {
    urls = 0;
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:${++urls}`);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("previews the picked file and drops it when the dialog reopens", async () => {
    const { wrapper, open } = await mountDialog();
    const avatar = () => wrapper.get("img").attributes("src");
    const saved = avatar();

    await pick(wrapper);
    expect(avatar()).toBe("blob:1");

    await open();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
    expect(avatar()).toBe(saved);
  });

  it("revokes the preview on unmount", async () => {
    const { wrapper } = await mountDialog();
    await pick(wrapper);

    wrapper.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });
});

describe("EditUserDialog age settings", () => {
  beforeEach(() => {
    fetchUserPermissions.mockResolvedValue(permissions());
    fetchCatalog.mockResolvedValue({ data: { entities: [], actions: [] } });
    getPlatforms.mockResolvedValue({ data: [] });
    updateUser.mockResolvedValue({
      data: userFixture({ id: 4, role: "user" }),
    });
    updateUserPermissions.mockResolvedValue({ data: {} });
  });

  async function save(wrapper: VueWrapper) {
    const apply = wrapper
      .findAll("button")
      .find((b) => b.text() === "common.apply");
    await apply?.trigger("click");
    await flushPromises();
  }

  it("sends the age settings only once they change", async () => {
    const { wrapper } = await mountDialog("user");
    const fields = wrapper.findComponent(AgeLimitFields);

    fields.vm.$emit("update:ageLimit", 12);
    await save(wrapper);

    expect(updateUserPermissions).toHaveBeenCalledExactlyOnceWith(
      4,
      expect.objectContaining({
        set_age_settings: true,
        age_limit: 12,
        hide_unrated_roms: null,
      }),
    );
  });

  it("keeps a slower load for an earlier user off the open one", async () => {
    let resolveFirst: (value: unknown) => void = () => undefined;
    fetchUserPermissions.mockReturnValueOnce(
      new Promise((resolve) => (resolveFirst = resolve)),
    );
    const { wrapper, open } = await mountDialog("user");
    const fields = () => wrapper.findComponent(AgeLimitFields);

    await open();
    resolveFirst(
      permissions({
        user_id: 3,
        age_limit: 12,
        hide_unrated_roms: true,
      }),
    );
    await flushPromises();

    expect(fields().props("ageLimit")).toBeNull();
    expect(fields().props("hideUnrated")).toBeNull();
  });

  it("shows the access fields only once they load", async () => {
    fetchUserPermissions.mockReturnValue(new Promise(() => undefined));
    const { wrapper } = await mountDialog("user");

    expect(wrapper.findComponent(AgeLimitFields).exists()).toBe(false);
    expect(wrapper.find("r-spinner-stub").exists()).toBe(true);
  });

  it("says when access failed to load and still saves the profile", async () => {
    fetchUserPermissions.mockRejectedValue(new Error("offline"));
    const { wrapper } = await mountDialog("user");

    expect(wrapper.findComponent(AgeLimitFields).exists()).toBe(false);
    expect(wrapper.text()).toContain("settings.access-load-error");
    await save(wrapper);

    expect(updateUser).toHaveBeenCalledOnce();
    expect(updateUserPermissions).not.toHaveBeenCalled();
  });

  it("saves the edits made before another user opens mid-save", async () => {
    let finishProfile: (value: unknown) => void = () => undefined;
    updateUser.mockReturnValueOnce(
      new Promise((resolve) => (finishProfile = resolve)),
    );
    const { wrapper, open } = await mountDialog("user");
    wrapper.findComponent(AgeLimitFields).vm.$emit("update:ageLimit", 12);
    const saving = save(wrapper);

    fetchUserPermissions.mockResolvedValue(
      permissions({ user_id: 7, age_limit: 16 }),
    );
    await open(7);
    finishProfile({ data: userFixture({ id: 4, role: "user" }) });
    await saving;

    expect(updateUserPermissions).toHaveBeenCalledExactlyOnceWith(
      4,
      expect.objectContaining({ age_limit: 12 }),
    );
  });

  it("keeps a dialog reopened mid-save open and editable", async () => {
    let finishProfile: (value: unknown) => void = () => undefined;
    updateUser.mockReturnValueOnce(
      new Promise((resolve) => (finishProfile = resolve)),
    );
    const { wrapper, open } = await mountDialog("user");
    const saving = save(wrapper);

    await open(7);
    finishProfile({ data: userFixture({ id: 4, role: "user" }) });
    await saving;

    const access = wrapper.get(".r-v2-user-dialog__access");
    expect(access.attributes("inert")).toBeUndefined();
  });

  it("locks the form while a save is in flight", async () => {
    let finishProfile: (value: unknown) => void = () => undefined;
    updateUser.mockReturnValueOnce(
      new Promise((resolve) => (finishProfile = resolve)),
    );
    const { wrapper } = await mountDialog("user");
    const access = () => wrapper.get(".r-v2-user-dialog__access");

    expect(access().attributes("inert")).toBeUndefined();
    const saving = save(wrapper);
    await flushPromises();
    expect(access().attributes()).toHaveProperty("inert");
    expect(
      wrapper.get(".r-v2-user-dialog__edit-grid").attributes(),
    ).toHaveProperty("inert");

    finishProfile({ data: userFixture({ id: 4, role: "user" }) });
    await saving;
  });

  it("leaves the permissions alone when nothing changed", async () => {
    const { wrapper } = await mountDialog("user");

    await save(wrapper);

    expect(updateUser).toHaveBeenCalledOnce();
    expect(updateUserPermissions).not.toHaveBeenCalled();
  });
});
