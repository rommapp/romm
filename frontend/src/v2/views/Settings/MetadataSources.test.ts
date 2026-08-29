/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import storeHeartbeat from "@/stores/heartbeat";
import MetadataSources from "./MetadataSources.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api", () => ({
  default: { get: vi.fn().mockResolvedValue({ data: true }) },
}));

vi.mock("@/stores/config", () => ({
  default: () => ({ fetchConfig: vi.fn() }),
}));

vi.mock("@v2/lib", () => ({
  RAlert: defineComponent({
    template:
      '<div class="alert"><slot name="title" /><slot /><slot name="append" /></div>',
  }),
  RBtn: defineComponent({ template: "<button><slot /></button>" }),
  RTag: defineComponent({
    props: { text: { type: String, default: "" } },
    template: "<span>{{ text }}</span>",
  }),
}));

vi.mock("@/v2/components/Settings/SettingsSection.vue", () => ({
  default: defineComponent({ template: "<section><slot /></section>" }),
}));

function mountWith(devCredentialsSet: boolean, loaded = true) {
  const heartbeat = storeHeartbeat();
  heartbeat.value.METADATA_SOURCES.SS_DEV_CREDENTIALS_SET = devCredentialsSet;
  heartbeat.loaded = loaded;
  return mount(MetadataSources);
}

describe("MetadataSources", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("warns when the build carries no ScreenScraper developer credentials", () => {
    const wrapper = mountWith(false);

    const alert = wrapper.find(".alert");
    expect(alert.exists()).toBe(true);
    expect(alert.text()).toContain(
      "settings.metadata-ss-dev-credentials-title",
    );
  });

  it("stays quiet when the developer credentials are present", () => {
    expect(mountWith(true).find(".alert").exists()).toBe(false);
  });

  it("stays quiet until a heartbeat has landed", () => {
    expect(mountWith(false, false).find(".alert").exists()).toBe(false);
  });
});
