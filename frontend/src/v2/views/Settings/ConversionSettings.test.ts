/* eslint-disable vue/one-component-per-file */
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import storeConfig, { type Config } from "@/stores/config";
import storeHeartbeat from "@/stores/heartbeat";
import ConversionSettings from "./ConversionSettings.vue";

const confirmFn = vi.fn();
const runTask = vi.fn();
const snackbarSuccess = vi.fn();
const scopes: string[] = [];

function useConfig(platformFormats: Record<string, string>) {
  const store = storeConfig();
  const config: Config = {
    ...store.config,
    CONFIG_FILE_MOUNTED: true,
    CONFIG_FILE_WRITABLE: true,
    CONVERTO: {
      download_conversion_enabled: true,
      cache_ttl_hours: 24,
      cache_max_size_gb: 20,
      platform_formats: platformFormats,
    },
    CONVERTO_LIBRARY_TARGETS: { psx: ["chd", "iso"], ngc: ["iso", "rvz"] },
  };
  store.config = config;
  vi.spyOn(store, "fetchConfig").mockResolvedValue(config);
}

vi.mock("vue-i18n");
vi.mock("vue-router", () => ({
  onBeforeRouteLeave: vi.fn(),
}));
vi.mock("@/services/api/config", () => ({
  default: { updateConvertoSettings: vi.fn() },
}));
vi.mock("@/services/api/task", () => ({
  default: { runTask: (name: string) => runTask(name) },
}));
vi.mock("@/stores/auth", () => ({
  default: () => ({ scopes }),
}));
vi.mock("@/stores/platforms", () => ({
  default: () => ({ allPlatforms: [] }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: snackbarSuccess, error: vi.fn() }),
}));
vi.mock("@v2/lib", () => ({
  RAlert: defineComponent({ template: "<div><slot /></div>" }),
  RBtn: defineComponent({
    props: { disabled: { type: Boolean, default: false } },
    emits: ["click"],
    template:
      '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
  }),
  RIcon: defineComponent({ template: "<i />" }),
  RSelect: defineComponent({
    props: { label: { type: String, default: "" } },
    template: '<select :aria-label="label" />',
  }),
  RSpinner: defineComponent({ template: "<span />" }),
  RTextField: defineComponent({ template: "<input />" }),
}));
vi.mock("@/v2/components/Settings/SettingsSection.vue", () => ({
  default: defineComponent({ template: "<section><slot /></section>" }),
}));
vi.mock("@/v2/components/Settings/SettingsToggleRow.vue", () => ({
  default: defineComponent({ template: "<div />" }),
}));

async function mountSettings() {
  const wrapper = mount(ConversionSettings);
  await flushPromises();
  return wrapper;
}

function convertButton(wrapper: Awaited<ReturnType<typeof mountSettings>>) {
  return wrapper
    .findAll("button")
    .find((b) => b.text() === "settings.conversion-convert-library");
}

describe("ConversionSettings", () => {
  beforeEach(() => {
    confirmFn.mockReset();
    runTask.mockReset();
    snackbarSuccess.mockReset();
    scopes.splice(0, scopes.length, "platforms.write", "tasks.run");
    setActivePinia(createPinia());
    storeHeartbeat().value.CONVERTO.ENABLED = true;
    useConfig({ psx: "chd" });
  });

  it("lists every platform that has a library format", async () => {
    const wrapper = await mountSettings();

    const labels = wrapper
      .findAll("select")
      .map((s) => s.attributes("aria-label"));
    expect(labels).toEqual(["ngc", "psx"]);
  });

  it("starts the convert library task once the typed confirmation passes", async () => {
    confirmFn.mockResolvedValue(true);
    const wrapper = await mountSettings();

    await convertButton(wrapper)?.trigger("click");
    await flushPromises();

    expect(confirmFn).toHaveBeenCalledWith(
      expect.objectContaining({
        tone: "danger",
        requireTyped: "rom.delete-keyword",
      }),
    );
    expect(runTask).toHaveBeenCalledWith("convert_library");
    expect(snackbarSuccess).toHaveBeenCalledOnce();
  });

  it("does nothing when the confirmation is cancelled", async () => {
    confirmFn.mockResolvedValue(false);
    const wrapper = await mountSettings();

    await convertButton(wrapper)?.trigger("click");
    await flushPromises();

    expect(runTask).not.toHaveBeenCalled();
  });

  it("stays disabled until a library format is saved", async () => {
    useConfig({});
    const wrapper = await mountSettings();

    expect(convertButton(wrapper)?.attributes("disabled")).toBeDefined();
  });

  it("warns and hides the convert button without rom-converto", async () => {
    storeHeartbeat().value.CONVERTO.ENABLED = false;
    const wrapper = await mountSettings();

    expect(wrapper.text()).toContain("settings.conversion-unavailable-desc");
    expect(convertButton(wrapper)).toBeUndefined();
  });

  it("is hidden without the tasks.run scope", async () => {
    scopes.splice(0, scopes.length, "platforms.write");
    const wrapper = await mountSettings();

    expect(convertButton(wrapper)).toBeUndefined();
  });
});
