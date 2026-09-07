import { describe, expect, it } from "vitest";
import type { Composer } from "vue-i18n";
import {
  buildSmartFilterCriteria,
  type GalleryFilterSnapshot,
  summarizeSmartFilterCriteria,
} from "./smartCollectionCriteria";

// Minimal i18n stub: returns the provided fallback (or the key). Cast to the
// real composer type since we only exercise the (key, fallback) overload.
const tStub = ((key: string, fallback?: string) =>
  fallback ?? key) as unknown as Composer["t"];

// Minimal "no filters set" snapshot; individual tests override fields.
function emptySnapshot(): GalleryFilterSnapshot {
  return {
    searchTerm: null,
    filterMatched: null,
    filterFavorites: null,
    filterDuplicates: null,
    filterPlayables: null,
    filterRA: null,
    filterSaves: null,
    filterStates: null,
    filterSoundtrack: null,
    filterMissing: null,
    filterPhysical: null,
    filterVerified: null,
    selectedPlatforms: [],
    selectedGenres: [],
    genresLogic: "any",
    selectedFranchises: [],
    franchisesLogic: "any",
    selectedCollections: [],
    collectionsLogic: "any",
    selectedCompanies: [],
    companiesLogic: "any",
    selectedPublishers: [],
    publishersLogic: "any",
    selectedDevelopers: [],
    developersLogic: "any",
    selectedAgeRatings: [],
    ageRatingsLogic: "any",
    selectedRegions: [],
    regionsLogic: "any",
    selectedLanguages: [],
    languagesLogic: "any",
    selectedPlayerCounts: [],
    playerCountsLogic: "any",
    selectedMetadataProviders: [],
    metadataProvidersLogic: "any",
    selectedTags: [],
    tagsLogic: "any",
    selectedStatuses: [],
    statusesLogic: "any",
  };
}

describe("buildSmartFilterCriteria — metadata providers", () => {
  it("serializes selected providers with their logic operator", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      selectedMetadataProviders: ["igdb", "moby"],
      metadataProvidersLogic: "all",
    });

    expect(out.metadata_providers).toEqual(["igdb", "moby"]);
    expect(out.metadata_providers_logic).toBe("all");
  });

  it("omits the keys entirely when no provider is selected", () => {
    const out = buildSmartFilterCriteria(emptySnapshot());

    expect(out.metadata_providers).toBeUndefined();
    expect(out.metadata_providers_logic).toBeUndefined();
  });

  it("surfaces providers in the human-readable summary", () => {
    const rows = summarizeSmartFilterCriteria(
      { metadata_providers: ["igdb"], metadata_providers_logic: "any" },
      tStub,
    );

    const row = rows.find((r) => r.key === "metadata_providers");
    expect(row).toBeDefined();
    expect(row?.values).toEqual(["igdb"]);
    expect(row?.logic).toBe("any");
  });
});

describe("buildSmartFilterCriteria — publishers and developers", () => {
  it("serializes publishers and developers with their logic operators", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      selectedPublishers: ["Atari"],
      publishersLogic: "any",
      selectedDevelopers: ["Artech Studios"],
      developersLogic: "all",
    });

    expect(out.publishers).toEqual(["Atari"]);
    expect(out.publishers_logic).toBe("any");
    expect(out.developers).toEqual(["Artech Studios"]);
    expect(out.developers_logic).toBe("all");
  });

  it("omits the keys entirely when neither is selected", () => {
    const out = buildSmartFilterCriteria(emptySnapshot());

    expect(out.publishers).toBeUndefined();
    expect(out.developers).toBeUndefined();
  });

  it("surfaces publishers and developers in the human-readable summary", () => {
    const rows = summarizeSmartFilterCriteria(
      {
        publishers: ["Atari"],
        publishers_logic: "any",
        developers: ["Artech Studios"],
        developers_logic: "any",
      },
      tStub,
    );

    expect(rows.find((r) => r.key === "publishers")?.values).toEqual(["Atari"]);
    expect(rows.find((r) => r.key === "developers")?.values).toEqual([
      "Artech Studios",
    ]);
  });
});

describe("buildSmartFilterCriteria — tags", () => {
  it("serializes selected tags with their logic operator", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      selectedTags: ["Proto", "Beta"],
      tagsLogic: "all",
    });

    expect(out.tags).toEqual(["Proto", "Beta"]);
    expect(out.tags_logic).toBe("all");
  });

  it("omits the keys entirely when no tag is selected", () => {
    const out = buildSmartFilterCriteria(emptySnapshot());

    expect(out.tags).toBeUndefined();
    expect(out.tags_logic).toBeUndefined();
  });

  it("surfaces tags in the human-readable summary", () => {
    const rows = summarizeSmartFilterCriteria(
      { tags: ["Proto"], tags_logic: "any" },
      tStub,
    );

    const row = rows.find((r) => r.key === "tags");
    expect(row).toBeDefined();
    expect(row?.values).toEqual(["Proto"]);
    expect(row?.logic).toBe("any");
  });
});

describe("buildSmartFilterCriteria — soundtrack", () => {
  it("serializes the soundtrack filter", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      filterSoundtrack: true,
    });

    expect(out.has_soundtrack).toBe(true);
  });

  it("surfaces the soundtrack filter in the human-readable summary", () => {
    const rows = summarizeSmartFilterCriteria({ has_soundtrack: true }, tStub);

    expect(rows).toContainEqual(
      expect.objectContaining({ key: "has_soundtrack" }),
    );
  });
});

describe("buildSmartFilterCriteria — saves and states", () => {
  it("serializes the saves and states filters", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      filterSaves: true,
      filterStates: true,
    });

    expect(out.has_saves).toBe(true);
    expect(out.has_states).toBe(true);
  });

  it("surfaces saves and states in the human-readable summary", () => {
    const rows = summarizeSmartFilterCriteria(
      { has_saves: true, has_states: true },
      tStub,
    );

    expect(rows).toContainEqual(expect.objectContaining({ key: "has_saves" }));
    expect(rows).toContainEqual(expect.objectContaining({ key: "has_states" }));
  });
});

describe("buildSmartFilterCriteria — negative tri-state filters", () => {
  it("serializes `false` states instead of dropping them", () => {
    const out = buildSmartFilterCriteria({
      ...emptySnapshot(),
      filterMatched: false,
      filterSaves: false,
    });

    expect(out.matched).toBe(false);
    expect(out.has_saves).toBe(false);
  });

  it("omits tri-state keys only when the filter is unset (null)", () => {
    const out = buildSmartFilterCriteria(emptySnapshot());

    expect(out.matched).toBeUndefined();
    expect(out.favorite).toBeUndefined();
    expect(out.has_saves).toBeUndefined();
    expect(out.has_states).toBeUndefined();
    expect(out.has_soundtrack).toBeUndefined();
  });

  it("renders `false` values with their negative label in the summary", () => {
    const rows = summarizeSmartFilterCriteria({ matched: false }, tStub);

    const row = rows.find((r) => r.key === "matched");
    expect(row).toBeDefined();
    expect(row?.label).toBe("Unmatched");
  });
});
