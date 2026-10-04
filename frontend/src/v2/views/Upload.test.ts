import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { platformFixture } from "@/utils/platform.fixtures";
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

vi.mock("vue-i18n");

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

const threeDo = platformFixture({
  id: -1,
  slug: "3do",
  name: "3DO Interactive Multiplayer",
  missing_from_fs: true,
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
    const zx80 = platformFixture({
      id: -1,
      slug: "zx80",
      name: "ZX80",
      missing_from_fs: true,
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
    scanning.scanning = false;
    scanning.startedInThisTab = false;
    getSupportedPlatforms.mockResolvedValueOnce({
      data: [{ ...threeDo, id: 7, missing_from_fs: false }],
    });
    uploadRoms.mockResolvedValueOnce([{ status: "fulfilled" }]);
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
