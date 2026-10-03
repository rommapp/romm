import { flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Events } from "@/types/emitter";
import { userFixture } from "@/utils/user.fixtures";
import EditUserDialog from "./EditUserDialog.vue";

vi.mock("vue-i18n");
// The access section loads behind the avatar; leave it pending.
vi.mock("@/services/api/permissions", () => ({
  default: {
    fetchUserPermissions: () => new Promise(() => undefined),
    fetchCatalog: () => new Promise(() => undefined),
  },
}));
vi.mock("@/services/api/platform", () => ({
  default: { getPlatforms: () => new Promise(() => undefined) },
}));
vi.mock("@/stores/permissionGroups", () => ({
  default: () => ({ groups: [], ensureLoaded: () => Promise.resolve() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /></div>`,
};

async function mountDialog() {
  const emitter: Emitter<Events> = mitt<Events>();
  const wrapper = mount(EditUserDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        RBtn: true,
        RIcon: true,
        RSelect: true,
        RSwitch: true,
        RTextField: true,
        HiddenGamesPicker: true,
        HiddenPlatformsPicker: true,
        OverridesMatrix: true,
      },
    },
  });
  const open = () => {
    emitter.emit("showEditUserDialog", userFixture({ id: 4 }));
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
