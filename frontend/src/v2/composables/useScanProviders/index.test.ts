import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";
import type { MetadataOption } from "@/stores/heartbeat";
import { useScanProviders, type HashMatcher } from "./index";

// Provider list the heartbeat would expose with every source enabled.
const OPTIONS: MetadataOption[] = [
  { value: "igdb", name: "IGDB", logo_path: "", disabled: "" },
  { value: "ss", name: "ScreenScraper", logo_path: "", disabled: "" },
  { value: "moby", name: "MobyGames", logo_path: "", disabled: "" },
  { value: "ra", name: "RetroAchievements", logo_path: "", disabled: "" },
  { value: "hasheous", name: "Hasheous", logo_path: "", disabled: "" },
  { value: "playmatch", name: "Playmatch", logo_path: "", disabled: "" },
];

const heartbeat = {
  value: {
    METADATA_SOURCES: {
      HASHEOUS_API_ENABLED: true,
      PLAYMATCH_API_ENABLED: true,
    },
  },
  getMetadataOptionsByPriority: () => OPTIONS,
};
const config = ref({ SKIP_HASH_CALCULATION: false });

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("pinia", () => ({
  storeToRefs: () => ({ config }),
}));
vi.mock("@/stores/config", () => ({ default: () => ({}) }));
vi.mock("@/stores/heartbeat", () => ({ default: () => heartbeat }));

beforeEach(() => {
  localStorage.clear();
  config.value.SKIP_HASH_CALCULATION = false;
});

describe("useScanProviders effective sources", () => {
  it("expands an All-mode group to its enabled providers", () => {
    const { effectiveMetadataSources } = useScanProviders();
    // Nothing stored ⇒ both selects boot in All-mode with an empty model.
    expect(effectiveMetadataSources.value.map((s) => s.value)).toEqual([
      "igdb",
      "ss",
      "moby",
      "ra",
    ]);
  });

  it("uses the explicit picks once a group has a selection", () => {
    const { metadataSources, generalAllSelected, effectiveMetadataSources } =
      useScanProviders();
    generalAllSelected.value = false;
    metadataSources.value = [OPTIONS[1]];
    expect(effectiveMetadataSources.value.map((s) => s.value)).toEqual([
      "ss",
      "ra",
    ]);
  });

  it("restores the stored picks once the provider list arrives", async () => {
    localStorage.setItem("scan.metadataSources", JSON.stringify(["moby"]));
    const { metadataSources } = useScanProviders();
    await nextTick();
    expect(metadataSources.value.map((s) => s.value)).toEqual(["moby"]);
  });

  it("keeps in-progress picks when only the option list changes", async () => {
    const { metadataSources, generalAllSelected } = useScanProviders();
    generalAllSelected.value = false;
    metadataSources.value = [OPTIONS[1]];
    // A heartbeat refresh re-emits the option list with fresh identities.
    config.value.SKIP_HASH_CALCULATION = true;
    await nextTick();
    expect(metadataSources.value.map((s) => s.value)).toEqual(["ss"]);
  });

  it("keeps hash matchers out of the provider selects", () => {
    const { generalProviders, specificProviders } = useScanProviders();
    const listed = [...generalProviders.value, ...specificProviders.value].map(
      (o) => o.value,
    );
    expect(listed).not.toContain("hasheous");
    expect(listed).not.toContain("playmatch");
  });
});

describe("useScanProviders Playmatch gate", () => {
  function playmatch(matchers: HashMatcher[]) {
    return matchers.find((m) => m.value === "playmatch")!;
  }

  it("is enabled when the general group is in All-mode (IGDB included)", () => {
    const { hashMatchers } = useScanProviders();
    expect(playmatch(hashMatchers.value).switchEnabled).toBe(true);
  });

  it("is enabled when IGDB is picked explicitly", () => {
    const { metadataSources, generalAllSelected, hashMatchers } =
      useScanProviders();
    generalAllSelected.value = false;
    metadataSources.value = [OPTIONS[0]];
    expect(playmatch(hashMatchers.value).switchEnabled).toBe(true);
  });

  it("is blocked when the picked providers exclude IGDB", () => {
    const { metadataSources, generalAllSelected, hashMatchers } =
      useScanProviders();
    generalAllSelected.value = false;
    metadataSources.value = [OPTIONS[1]];
    const matcher = playmatch(hashMatchers.value);
    expect(matcher.switchEnabled).toBe(false);
    expect(matcher.blockedReason).toBe("scan.playmatch-requires-igdb");
  });

  it("is blocked when hash calculation is off", () => {
    config.value.SKIP_HASH_CALCULATION = true;
    const { hashMatchers } = useScanProviders();
    const matcher = playmatch(hashMatchers.value);
    expect(matcher.switchEnabled).toBe(false);
    expect(matcher.blockedReason).toBe("scan.requires-hashes");
  });
});

describe("useScanProviders scan payload", () => {
  it("sends the expanded provider list and the playmatch flag", () => {
    const { buildScanPayload } = useScanProviders();
    expect(buildScanPayload()).toEqual({
      apis: ["igdb", "ss", "moby", "ra", "hasheous"],
      launchbox_remote_enabled: true,
      playmatch_enabled: true,
    });
  });

  it("drops both hash matchers when hashing is disabled", () => {
    config.value.SKIP_HASH_CALCULATION = true;
    const { buildScanPayload } = useScanProviders();
    const payload = buildScanPayload();
    expect(payload.apis).not.toContain("hasheous");
    expect(payload.playmatch_enabled).toBe(false);
  });

  it("persists the explicit picks, leaving All-mode groups empty", async () => {
    const { metadataSources, generalAllSelected, persistSelection } =
      useScanProviders();
    generalAllSelected.value = false;
    metadataSources.value = [OPTIONS[0]];
    persistSelection();
    await nextTick();
    expect(
      JSON.parse(localStorage.getItem("scan.metadataSources") ?? "[]"),
    ).toEqual(["igdb"]);
  });
});
