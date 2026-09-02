/* eslint-disable vue/one-component-per-file */
import { type DOMWrapper, mount } from "@vue/test-utils";
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
  default: defineComponent({
    props: { title: { type: String, default: "" } },
    template: '<section :data-title="title"><slot /></section>',
  }),
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

  // The split has to keep matching useScanProviders' general/specific sets,
  // which drive the same providers in the scan dialog.
  it.each([
    ["settings.metadata-catalogs", ["IGDB", "ScreenScraper", "Steam"]],
    ["settings.metadata-specialised", ["RetroAchievements", "SteamGridDB"]],
    ["settings.metadata-proxies", ["Hasheous", "PlayMatch"]],
  ])("groups %s tiles under their own section", (title, names) => {
    const wrapper = mountWith(true);

    const tileNames = (section: DOMWrapper<Element>) =>
      section.findAll(".r-v2-meta__name").map((n) => n.text());

    const sections = wrapper.findAll("section");
    const section = sections.find((s) => s.attributes("data-title") === title);
    expect(section).toBeDefined();

    const elsewhere = sections
      .filter((s) => s.attributes("data-title") !== title)
      .flatMap(tileNames);
    for (const name of names) {
      expect(tileNames(section!)).toContain(name);
      expect(elsewhere).not.toContain(name);
    }
  });
});
