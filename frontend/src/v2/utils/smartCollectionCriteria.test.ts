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
    filterMissing: null,
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
