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
  age_exempt_rom_ids: [5],
};

beforeEach(() => {
  createGroup.mockResolvedValue({ data: { ...group, id: 8 } });
  updateGroup.mockResolvedValue({ data: group });
});

async function openDialog(toEdit: PermissionGroupSchema | null) {
  const emitter: Emitter<Events> = mitt<Events>();
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
        age_exempt_rom_ids: null,
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
        age_exempt_rom_ids: null,
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
      age_exempt_rom_ids: [],
    });
    expect(body).not.toHaveProperty("set_age_settings");
  });
});
