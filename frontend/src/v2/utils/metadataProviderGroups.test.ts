// Contract test for the provider taxonomy: the four grouping surfaces must
// agree, and an unclassified provider silently disappears from the scan selects.
/* eslint-disable vue/one-component-per-file */
import { mount, type VueWrapper } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick } from "vue";
import storeHeartbeat from "@/stores/heartbeat";
import SetupStepMetadata from "@/v2/components/Auth/SetupStepMetadata.vue";
import ScanInfoDialog from "@/v2/components/Scan/ScanInfoDialog.vue";
import { useScanProviders } from "@/v2/composables/useScanProviders";
import { METADATA_PROVIDER_FILTER_OPTIONS } from "@/v2/utils/metadataProviders";
import MetadataSources from "@/v2/views/Settings/MetadataSources.vue";
import {
  groupProviders,
  METADATA_PROVIDER_GROUP_ORDER,
  METADATA_PROVIDER_GROUPS,
  metadataProviderGroup,
  providerKeysInGroup,
  SETUP_GROUP_LABELS,
} from "./metadataProviderGroups";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/services/api", () => ({
  default: { get: vi.fn().mockResolvedValue({ data: {} }) },
}));

vi.mock("@v2/lib", () => {
  const slotHost = (tag: string) =>
    defineComponent({ template: `<${tag}><slot /></${tag}>` });
  return {
    RAlert: slotHost("div"),
    RAvatar: slotHost("span"),
    RBtn: slotHost("button"),
    RDialog: defineComponent({
      template: "<div><slot name='toolbar' /><slot name='content' /></div>",
    }),
    RIcon: slotHost("i"),
    RImg: slotHost("span"),
    RTabNav: defineComponent({ name: "RTabNav", template: "<nav />" }),
    RTag: slotHost("span"),
  };
});

vi.mock("@/v2/components/Settings/SettingsSection.vue", () => ({
  default: defineComponent({ template: "<section><slot /></section>" }),
}));

/** Provider key → group, as the rendered surface actually lays it out. */
function renderedGroups(wrapper: VueWrapper): Record<string, string> {
  const groups: Record<string, string> = {};
  for (const section of wrapper.findAll("[data-group]")) {
    const group = section.attributes("data-group");
    for (const row of section.findAll("[data-provider]")) {
      const key = row.attributes("data-provider");
      if (group && key) groups[key] = group;
    }
  }
  return groups;
}

/** The scan info dialog opens on its "scan types" tab; the provider
 *  sections live behind the second one. */
async function providersTab(): Promise<VueWrapper> {
  const wrapper = mount(ScanInfoDialog, { props: { modelValue: true } });
  wrapper
    .findComponent({ name: "RTabNav" })
    .vm.$emit("update:modelValue", "providers");
  await nextTick();
  return wrapper;
}

beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
});

describe("metadata provider taxonomy", () => {
  it("classifies every provider the heartbeat exposes", () => {
    const unclassified = storeHeartbeat()
      .getAllMetadataOptions()
      .map((option) => option.value)
      .filter((value) => !metadataProviderGroup(value));
    expect(unclassified).toEqual([]);
  });

  it("leaves an inherited property unclassified", () => {
    expect(metadataProviderGroup("toString")).toBeUndefined();
    expect(metadataProviderGroup("constructor")).toBeUndefined();
  });

  it("classifies every provider the ROM match registry lists", () => {
    const unclassified = METADATA_PROVIDER_FILTER_OPTIONS.map(
      (option) => option.value,
    ).filter((value) => !metadataProviderGroup(value));
    expect(unclassified).toEqual([]);
  });
});

describe("metadata provider surfaces", () => {
  it("splits the scan selects by the taxonomy", () => {
    const { generalProviders, specificProviders } = useScanProviders();
    expect(generalProviders.value.map((o) => o.value).sort()).toEqual(
      providerKeysInGroup("catalog").sort(),
    );
    expect(specificProviders.value.map((o) => o.value).sort()).toEqual(
      providerKeysInGroup("specialised").sort(),
    );
  });

  it("groups the providers it renders the same way everywhere", async () => {
    // The reference surfaces carry a description and links per provider, so
    // they cover fewer providers than the scan selects, but the same ones.
    const wizard = renderedGroups(mount(SetupStepMetadata));
    const settings = renderedGroups(mount(MetadataSources));
    const scanInfo = renderedGroups(await providersTab());

    expect(Object.keys(wizard).length).toBeGreaterThan(0);
    expect(settings).toEqual(wizard);
    expect(scanInfo).toEqual(wizard);

    for (const [key, group] of Object.entries(wizard)) {
      expect(group).toBe(metadataProviderGroup(key));
    }
  });
});

describe("providerKeysInGroup", () => {
  it("partitions the taxonomy across the rendered section order", () => {
    const partitioned = METADATA_PROVIDER_GROUP_ORDER.flatMap((group) =>
      providerKeysInGroup(group),
    );
    expect(partitioned.sort()).toEqual(
      Object.keys(METADATA_PROVIDER_GROUPS).sort(),
    );
  });
});

describe("groupProviders", () => {
  it("sections the providers in render order and merges their labels", () => {
    const sections = groupProviders(
      [{ key: "playmatch" as const }, { key: "igdb" as const }],
      SETUP_GROUP_LABELS,
    );

    expect(sections.map((section) => section.group)).toEqual([
      ...METADATA_PROVIDER_GROUP_ORDER,
    ]);
    expect(
      sections.map((section) => section.providers.map((p) => p.key)),
    ).toEqual([["igdb"], [], ["playmatch"]]);
    expect(sections[0].titleKey).toBe(SETUP_GROUP_LABELS.catalog.titleKey);
  });
});
