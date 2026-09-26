import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import type { Platform } from "@/stores/platforms";
import Upload from "./Upload.vue";

const {
  getSupportedPlatforms,
  uploadPlatform,
  uploadRoms,
  emit,
  warning,
  scanning,
} = vi.hoisted(() => ({
  getSupportedPlatforms: vi.fn(),
  uploadPlatform: vi.fn(),
  uploadRoms: vi.fn(),
  emit: vi.fn(),
  warning: vi.fn(),
  scanning: {
    scanning: false,
    startedInThisTab: false,
    setScanning(value: boolean) {
      this.scanning = value;
    },
  },
}));

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
  default: { connected: true, connect: vi.fn(), emit },
}));

vi.mock("@/stores/heartbeat", () => ({
  default: () => ({ getEnabledMetadataOptions: () => [] }),
}));

vi.mock("@/stores/scanning", () => ({
  default: () => scanning,
}));

vi.mock("@/stores/upload", () => ({
  default: () => ({ reset: vi.fn() }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    error: vi.fn(),
    success: vi.fn(),
    warning,
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

const stubs = {
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
};

const threeDo = platform({
  slug: "3do",
  fs_slug: "3do",
  name: "3DO Interactive Multiplayer",
  display_name: "3DO Interactive Multiplayer",
});

async function uploadOneFile() {
  const wrapper = mount(Upload, { global: { stubs } });
  await flushPromises();
  await wrapper.get(".platform-select").trigger("click");
  await wrapper.get(".dropzone").trigger("click");
  await nextTick();
  await wrapper.get(".upload").trigger("click");
  await flushPromises();
  return wrapper;
}

describe("Upload platform selection", () => {
  it("uses the unique slug when unsupported platforms share sentinel id -1", async () => {
    const zx80 = platform({
      slug: "zx80",
      fs_slug: "zx80",
      name: "ZX80",
      display_name: "ZX80",
    });
    getSupportedPlatforms.mockResolvedValueOnce({ data: [zx80, threeDo] });
    uploadPlatform.mockResolvedValueOnce({ data: { ...threeDo, id: 123 } });
    uploadRoms.mockResolvedValueOnce([{ status: "fulfilled" }]);

    const wrapper = await uploadOneFile();

    expect(wrapper.get(".platform-select").attributes("data-item-key")).toBe(
      "slug",
    );
    expect(uploadPlatform).toHaveBeenCalledWith({ fsSlug: "3do" });
    expect(uploadRoms).toHaveBeenCalledWith({
      platformId: 123,
      filesToUpload: [expect.objectContaining({ name: "game.rom" })],
    });
  });
});

describe("Upload follow-up scan", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout"] });
    emit.mockClear();
    warning.mockClear();
    scanning.scanning = false;
    scanning.startedInThisTab = false;
    getSupportedPlatforms.mockResolvedValueOnce({
      data: [{ ...threeDo, id: 7, missing_from_fs: false }],
    });
    uploadRoms.mockResolvedValueOnce([{ status: "fulfilled" }]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("scans the platform once the upload lands", async () => {
    await uploadOneFile();
    vi.runAllTimers();

    expect(emit).toHaveBeenCalledOnce();
    expect(emit).toHaveBeenCalledWith("scan", {
      platforms: [7],
      type: "quick",
      apis: [],
    });
  });

  it("does not request a second scan while one is running", async () => {
    await uploadOneFile();
    scanning.scanning = true;
    vi.runAllTimers();

    expect(emit).not.toHaveBeenCalled();
    expect(warning).toHaveBeenCalledWith(
      "scan.scan-in-progress",
      expect.anything(),
    );
  });
});
