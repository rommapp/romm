import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DetailedRomSchema } from "@/__generated__";
import PatcherTab from "./PatcherTab.vue";

const { post } = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("pinia", async (importOriginal) => ({
  ...(await importOriginal<typeof import("pinia")>()),
  storeToRefs: (store: object) => store,
}));
vi.mock("@/services/api", () => ({ default: { post } }));
vi.mock("@/services/api/rom", () => ({
  default: { uploadRoms: vi.fn() },
}));
vi.mock("@/services/socket", () => ({
  default: { connected: true, connect: vi.fn(), emit: vi.fn() },
}));
vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ getEnabledMetadataOptions: () => [] }),
}));
vi.mock("@/stores/platforms", () => ({
  default: () => ({ filteredPlatforms: { value: [] } }),
}));
vi.mock("@/stores/scanning", () => ({
  default: () => ({ setScanning: vi.fn() }),
}));
vi.mock("@/stores/upload", () => ({
  default: () => ({ reset: vi.fn() }),
}));
vi.mock("@/v2/composables/useCan", async () => {
  const { ref } = await import("vue");
  return { useCan: () => ref(false) };
});
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), warning: vi.fn() }),
}));

const RSelect = {
  props: {
    modelValue: { type: String, default: "" },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue"],
  template: `<select :value="modelValue" @change="$emit('update:modelValue', $event.target.value)"><option v-for="item in items" :key="item.name" :value="item.name">{{ item.name }}</option></select>`,
};
const RBtn = {
  props: { disabled: { type: Boolean, default: false } },
  emits: ["click"],
  template: `<button :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function rom(): DetailedRomSchema {
  return {
    id: 1,
    name: "Super Metroid",
    fs_name: "Super Metroid.zip",
    platform_id: 2,
    platform_slug: "snes",
    platform_fs_slug: "snes",
    platform_display_name: "Super Nintendo Entertainment System",
    missing_from_fs: false,
    files: [
      {
        id: 10,
        category: "game",
        file_name: "Super Metroid.zip",
        file_size_bytes: 100,
        archive_members: [
          {
            name: "docs/readme.txt",
            size: 10,
            crc_hash: "",
            md5_hash: "",
            sha1_hash: "",
          },
          {
            name: "roms/Super Metroid.sfc",
            size: 90,
            crc_hash: "",
            md5_hash: "",
            sha1_hash: "",
          },
        ],
      },
      {
        id: 11,
        category: "patch",
        file_name: "translation.bps",
        file_size_bytes: 10,
        archive_members: null,
      },
    ],
  } as DetailedRomSchema;
}

describe("PatcherTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    post.mockResolvedValue({ data: new Blob(["patched"]), headers: {} });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  it("sends the selected ZIP member when applying a patch", async () => {
    const wrapper = mount(PatcherTab, {
      props: { rom: rom() },
      global: {
        stubs: {
          RAlert: true,
          RBtn,
          RCheckbox: true,
          RDropzone: true,
          RExpandTransition: { template: "<div><slot /></div>" },
          RIcon: true,
          RPlatformIcon: true,
          RSelect,
          RSliderBtnGroup: true,
          RTextField: true,
          RTooltip: true,
          MissingFSBadge: true,
          PlatformSelect: true,
        },
      },
    });

    const applyButton = wrapper.get("button");
    expect(applyButton.attributes("disabled")).toBeDefined();

    await wrapper.get("select").setValue("roms/Super Metroid.sfc");
    expect(applyButton.attributes("disabled")).toBeUndefined();
    await applyButton.trigger("click");
    await flushPromises();

    const request = post.mock.calls[0];
    expect(request[0]).toBe("/roms/10/patch");
    expect((request[1] as FormData).get("patch_file_id")).toBe("11");
    expect((request[1] as FormData).get("archive_member_name")).toBe(
      "roms/Super Metroid.sfc",
    );
  });
});
