import { RTextField } from "@v2/lib";
import { type VueWrapper, flushPromises, mount } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PermissionGroupSchema } from "@/__generated__";
import type { Events } from "@/types/emitter";
import AgeLimitFields from "./AgeLimitFields.vue";
import GroupFormDialog from "./GroupFormDialog.vue";

const { createGroup, updateGroup } = vi.hoisted(() => ({
  createGroup: vi.fn(),
  updateGroup: vi.fn(),
}));

vi.mock("vue-i18n");
vi.mock("@/services/api/permissions", () => ({
  default: {
    fetchCatalog: () =>
      Promise.resolve({ data: { entities: [], actions: [] } }),
    createGroup,
    updateGroup,
  },
}));
vi.mock("@/services/api/platform", () => ({
  default: { getPlatforms: () => Promise.resolve({ data: [] }) },
}));
vi.mock("@/stores/permissionGroups", () => ({
  default: () => ({ fetch: () => Promise.resolve() }),
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="content" /><slot name="footer" /></div>`,
};

const group: PermissionGroupSchema = {
  id: 7,
  name: "Kids",
  description: "",
  is_default: false,
  system_key: null,
  color: null,
  grants: [],
  member_count: 1,
  age_limit: 12,
  hide_unrated_roms: true,
};

beforeEach(() => {
  createGroup.mockResolvedValue({ data: { ...group, id: 8 } });
  updateGroup.mockResolvedValue({ data: group });
});

let emitter: Emitter<Events>;

async function openDialog(toEdit: PermissionGroupSchema | null) {
  emitter = mitt<Events>();
  const wrapper = mount(GroupFormDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog,
        RBtn: {
          emits: ["click"],
          template: `<button @click="$emit('click')"><slot /></button>`,
        },
        RIcon: true,
        RSwitch: true,
        RTextField: true,
        PermissionsMatrix: true,
        HiddenGamesPicker: true,
        HiddenPlatformsPicker: true,
        AgeLimitFields: true,
      },
    },
  });
  emitter.emit("showGroupFormDialog", toEdit);
  await flushPromises();
  return wrapper;
}

async function apply(wrapper: VueWrapper) {
  // Let the Apply button re-render once a name enables it.
  await flushPromises();
  const button = wrapper
    .findAll("button")
    .find((b) => b.text() === "common.apply");
  await button?.trigger("click");
  await flushPromises();
}

describe("GroupFormDialog age settings", () => {
  it("loads a group's settings and writes back the ones that change", async () => {
    const wrapper = await openDialog(group);
    const fields = wrapper.findComponent(AgeLimitFields);
    expect(fields.props("ageLimit")).toBe(12);
    expect(fields.props("hideUnrated")).toBe(true);

    fields.vm.$emit("update:ageLimit", null);
    await apply(wrapper);

    expect(updateGroup).toHaveBeenCalledExactlyOnceWith(
      7,
      expect.objectContaining({
        set_age_settings: true,
        age_limit: null,
        hide_unrated_roms: true,
      }),
    );
  });

  it("leaves the age settings alone on a rename", async () => {
    const wrapper = await openDialog(group);
    wrapper.findComponent(RTextField).vm.$emit("update:modelValue", "Teens");
    await apply(wrapper);

    expect(updateGroup).toHaveBeenCalledExactlyOnceWith(
      7,
      expect.objectContaining({
        name: "Teens",
        set_age_settings: false,
      }),
    );
  });

  it("creates a group with the settings and no update flag", async () => {
    const wrapper = await openDialog(null);
    wrapper.findComponent(RTextField).vm.$emit("update:modelValue", "Teens");
    wrapper.findComponent(AgeLimitFields).vm.$emit("update:ageLimit", 16);
    await apply(wrapper);

    const body = createGroup.mock.calls[0]?.[0];
    expect(body).toMatchObject({
      name: "Teens",
      age_limit: 16,
      hide_unrated_roms: false,
    });
    expect(body).not.toHaveProperty("set_age_settings");
  });

  it("locks the form while a save is in flight", async () => {
    let finish: (value: unknown) => void = () => undefined;
    updateGroup.mockReturnValueOnce(
      new Promise((resolve) => (finish = resolve)),
    );
    const wrapper = await openDialog(group);
    const form = () => wrapper.get(".r-v2-group-dialog__form");

    expect(form().attributes("inert")).toBeUndefined();
    await apply(wrapper);
    expect(form().attributes()).toHaveProperty("inert");

    finish({ data: group });
    await flushPromises();
  });

  it("keeps a dialog reopened mid-save open and editable", async () => {
    let finish: (value: unknown) => void = () => undefined;
    updateGroup.mockReturnValueOnce(
      new Promise((resolve) => (finish = resolve)),
    );
    const wrapper = await openDialog(group);
    await apply(wrapper);

    emitter.emit("showGroupFormDialog", { ...group, id: 9, name: "Teens" });
    await flushPromises();
    finish({ data: group });
    await flushPromises();

    const form = wrapper.get(".r-v2-group-dialog__form");
    expect(form.attributes("inert")).toBeUndefined();
  });
});
