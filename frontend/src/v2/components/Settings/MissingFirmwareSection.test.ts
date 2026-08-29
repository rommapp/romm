import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storePlatforms from "@/stores/platforms";
import MissingFirmwareSection from "./MissingFirmwareSection.vue";

const { getFirmware, runTask, getTaskById, confirm } = vi.hoisted(() => ({
  getFirmware: vi.fn(),
  runTask: vi.fn(),
  getTaskById: vi.fn(),
  confirm: vi.fn(),
}));

vi.mock("@/services/api/firmware", () => ({ default: { getFirmware } }));
vi.mock("@/services/api/task", () => ({ default: { runTask, getTaskById } }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirm,
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const PS1 = {
  id: 1,
  slug: "ps",
  name: "PlayStation",
  display_name: "PlayStation",
};
const SATURN = {
  id: 2,
  slug: "saturn",
  name: "Sega Saturn",
  display_name: "Sega Saturn",
};

function firmware(id: number, platformId: number, fileName: string) {
  return {
    id,
    platform_id: platformId,
    file_name: fileName,
    file_path: "bios",
    file_size_bytes: 512,
    missing_from_fs: true,
  };
}

function seedPlatforms() {
  storePlatforms().allPlatforms = [PS1, SATURN] as never;
}

// The kebab's items live in RMenu's default slot; the auto-stub drops slot
// content, so render it to reach the cleanup action.
const RMenuStub = {
  name: "RMenu",
  template: '<div><slot name="activator" :props="{}" /><slot /></div>',
};

function mountSection() {
  return mount(MissingFirmwareSection, {
    global: {
      stubs: {
        CachedPlatformIcon: true,
        RBtn: true,
        RIcon: true,
        RMenu: RMenuStub,
        RMenuItem: true,
        RSelect: true,
        RTag: true,
      },
    },
  });
}

async function selectPlatforms(
  wrapper: ReturnType<typeof mountSection>,
  ids: number[],
) {
  wrapper
    .findComponent({ name: "PlatformSelect" })
    .vm.$emit("update:modelValue", ids);
  await flushPromises();
}

describe("MissingFirmwareSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    seedPlatforms();
    runTask.mockReset();
    runTask.mockResolvedValue({ data: { task_id: "job-1" } });
    getTaskById.mockReset();
    getTaskById.mockResolvedValue({ data: { status: "finished" } });
    confirm.mockReset();
    confirm.mockResolvedValue(true);
    getFirmware.mockReset();
    getFirmware.mockResolvedValue({
      data: [firmware(10, PS1.id, "scph5501.bin")],
    });
  });

  it("asks the server for missing firmware only", async () => {
    mountSection();
    await flushPromises();

    expect(getFirmware).toHaveBeenCalledTimes(1);
    expect(getFirmware.mock.calls[0][0]).toMatchObject({ missing: true });
  });

  it("renders one row per missing entry", async () => {
    getFirmware.mockResolvedValue({
      data: [
        firmware(10, PS1.id, "scph5501.bin"),
        firmware(11, SATURN.id, "saturn_bios.bin"),
      ],
    });

    const wrapper = mountSection();
    await flushPromises();

    const rows = wrapper.findAll("[data-test='missing-firmware-row']");
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain("scph5501.bin");
  });

  it("filters by platform client-side rather than refetching", async () => {
    getFirmware.mockResolvedValue({
      data: [
        firmware(10, PS1.id, "scph5501.bin"),
        firmware(11, SATURN.id, "saturn_bios.bin"),
      ],
    });

    const wrapper = mountSection();
    await flushPromises();
    getFirmware.mockClear();

    await selectPlatforms(wrapper, [SATURN.id]);

    const rows = wrapper.findAll("[data-test='missing-firmware-row']");
    expect(rows).toHaveLength(1);
    expect(rows[0].text()).toContain("saturn_bios.bin");
    expect(getFirmware).not.toHaveBeenCalled();
  });

  it("scopes the cleanup task to a single selected platform", async () => {
    const wrapper = mountSection();
    await flushPromises();
    await selectPlatforms(wrapper, [PS1.id]);

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(runTask).toHaveBeenCalledWith("cleanup_missing_firmware", {
      platform_ids: [PS1.id],
    });
  });

  // The confirm dialog names every selected platform, so the cleanup has to
  // delete exactly those rather than falling back to the whole library.
  it("scopes the cleanup task to every selected platform", async () => {
    const wrapper = mountSection();
    await flushPromises();
    await selectPlatforms(wrapper, [PS1.id, SATURN.id]);

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(runTask).toHaveBeenCalledWith("cleanup_missing_firmware", {
      platform_ids: [PS1.id, SATURN.id],
    });
  });

  it("runs the unscoped cleanup when no platform is selected", async () => {
    const wrapper = mountSection();
    await flushPromises();

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(runTask).toHaveBeenCalledWith("cleanup_missing_firmware", {});
  });

  it("waits for the cleanup task to finish before reloading the list", async () => {
    const wrapper = mountSection();
    await flushPromises();
    getFirmware.mockClear();
    getFirmware.mockResolvedValue({ data: [] });

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(getTaskById).toHaveBeenCalledWith("job-1");
    expect(getFirmware).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[data-test='missing-firmware-empty']").exists()).toBe(
      true,
    );
  });

  it("leaves the list alone while the cleanup task is still running", async () => {
    getTaskById.mockResolvedValue({ data: { status: "started" } });

    const wrapper = mountSection();
    await flushPromises();
    getFirmware.mockClear();

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(getFirmware).not.toHaveBeenCalled();
  });

  it("does not queue anything when the confirmation is declined", async () => {
    confirm.mockResolvedValue(false);

    const wrapper = mountSection();
    await flushPromises();

    wrapper.findComponent({ name: "RMenuItem" }).vm.$emit("click");
    await flushPromises();

    expect(runTask).not.toHaveBeenCalled();
  });

  it("shows the empty state when nothing is missing", async () => {
    getFirmware.mockResolvedValue({ data: [] });

    const wrapper = mountSection();
    await flushPromises();

    expect(wrapper.find("[data-test='missing-firmware-empty']").exists()).toBe(
      true,
    );
    expect(wrapper.findAll("[data-test='missing-firmware-row']")).toHaveLength(
      0,
    );
  });
});
