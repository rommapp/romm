import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PasswordField from "@/components/shared/PasswordField.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import ChangePasswordDialog from "./ChangePasswordDialog.vue";

vi.mock("vue-i18n");
vi.mock("@/services/api/user", () => ({ default: { updateUser: vi.fn() } }));
vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};

function mountDialog(userId: number) {
  return mount(ChangePasswordDialog, {
    props: { open: true, userId },
    global: {
      stubs: {
        RDialog,
        RBtn: {
          emits: ["click"],
          template: `<button @click="$emit('click')"><slot /></button>`,
        },
        RIcon: true,
        RTextField: true,
      },
    },
  });
}

function field(wrapper: ReturnType<typeof mountDialog>, autocomplete: string) {
  return wrapper
    .findAllComponents(PasswordField)
    .filter((f) => f.props("autocomplete") === autocomplete);
}

async function fill(wrapper: ReturnType<typeof mountDialog>, current?: string) {
  for (const f of field(wrapper, "new-password")) {
    f.vm.$emit("update:modelValue", "new_pass");
  }
  if (current !== undefined) {
    field(wrapper, "current-password")[0]?.vm.$emit(
      "update:modelValue",
      current,
    );
  }
  await flushPromises();
}

const confirm = (wrapper: ReturnType<typeof mountDialog>) =>
  wrapper.get("button");

describe("ChangePasswordDialog", () => {
  beforeEach(() => {
    vi.mocked(userApi.updateUser).mockResolvedValue({
      data: userFixture({ id: 1 }),
    } as never);
  });

  it("sends the current password with the new one", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    const wrapper = mountDialog(1);

    await fill(wrapper);
    expect(confirm(wrapper).attributes()).toHaveProperty("disabled");

    await fill(wrapper, "old_pass");
    await confirm(wrapper).trigger("click");
    await flushPromises();

    expect(userApi.updateUser).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      password: "new_pass",
      current_password: "old_pass",
    });
  });

  it("sets a first password without one on an account with none", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1, has_password: false }));
    const wrapper = mountDialog(1);

    expect(field(wrapper, "current-password")).toHaveLength(0);
    await fill(wrapper);
    await confirm(wrapper).trigger("click");
    await flushPromises();

    expect(userApi.updateUser).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      password: "new_pass",
      current_password: undefined,
    });
  });
});
