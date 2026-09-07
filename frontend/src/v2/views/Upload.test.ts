import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { Platform } from "@/stores/platforms";
import Upload from "./Upload.vue";

const { getSupportedPlatforms, uploadPlatform, uploadRoms } = vi.hoisted(
  () => ({
    getSupportedPlatforms: vi.fn(),
    uploadPlatform: vi.fn(),
    uploadRoms: vi.fn(),
  }),
);

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => ({ query: {} }),
}));

vi.mock("@/services/api/platform", () => ({
  default: {
    getSupportedPlatforms,
    uploadPlatform,
  },
}));

vi.mock("@/services/api/rom", () => ({
  default: { uploadRoms },
}));

vi.mock("@/services/socket", () => ({
  default: { connected: true, connect: vi.fn(), emit: vi.fn() },
}));

vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ getEnabledMetadataOptions: () => [] }),
}));

vi.mock("@/stores/scanning", () => ({
  default: () => ({ setScanning: vi.fn() }),
}));

vi.mock("@/stores/upload", () => ({
  default: () => ({ reset: vi.fn() }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    error: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
  }),
}));

function platform(overrides: Partial<Platform>): Platform {
  return {
    id: -1,
    slug: "platform",
    fs_slug: "platform",
    rom_count: 0,
    name: "Platform",
    igdb_slug: null,
    moby_slug: null,
    hltb_slug: null,
    libretro_slug: null,
    created_at: "",
    updated_at: "",
    fs_size_bytes: 0,
    is_unidentified: false,
    is_identified: true,
    missing_from_fs: true,
    display_name: "Platform",
    firmware_count: 0,
    ...overrides,
  };
}

describe("Upload platform selection", () => {
  it("uses the unique slug when unsupported platforms share sentinel id -1", async () => {
    const threeDo = platform({
      slug: "3do",
      fs_slug: "3do",
      name: "3DO Interactive Multiplayer",
      display_name: "3DO Interactive Multiplayer",
    });
    const zx80 = platform({
      slug: "zx80",
      fs_slug: "zx80",
      name: "ZX80",
      display_name: "ZX80",
    });
    getSupportedPlatforms.mockResolvedValueOnce({ data: [zx80, threeDo] });
    uploadPlatform.mockResolvedValueOnce({ data: { ...threeDo, id: 123 } });
    uploadRoms.mockResolvedValueOnce([{ status: "fulfilled" }]);

    const wrapper = mount(Upload, {
      global: {
        stubs: {
          PlatformSelect: {
            props: ["modelValue", "items", "itemKey"],
            emits: ["update:modelValue"],
            template:
              '<button class="platform-select" :data-item-key="itemKey" @click="$emit(\'update:modelValue\', \'3do\')" />',
          },
          RDropzone: {
            emits: ["files"],
            template:
              "<button class=\"dropzone\" @click=\"$emit('files', [{ name: 'game.rom', size: 3 }])\" />",
          },
          RBtn: {
            props: ["disabled"],
            emits: ["click"],
            template:
              '<button class="upload" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
          },
          RChip: true,
          RIcon: true,
        },
      },
    });

    await flushPromises();
    expect(wrapper.get(".platform-select").attributes("data-item-key")).toBe(
      "slug",
    );

    await wrapper.get(".platform-select").trigger("click");
    await wrapper.get(".dropzone").trigger("click");
    await nextTick();
    await wrapper.get(".upload").trigger("click");
    await flushPromises();

    expect(uploadPlatform).toHaveBeenCalledWith({ fsSlug: "3do" });
    expect(uploadRoms).toHaveBeenCalledWith({
      platformId: 123,
      filesToUpload: [expect.objectContaining({ name: "game.rom" })],
    });
  });
});
