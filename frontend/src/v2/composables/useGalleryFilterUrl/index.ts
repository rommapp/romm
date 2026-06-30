// useGalleryFilterUrl — bookmarkable gallery filters via URL query
// params. Round-trips between Vue Router's `route.query` and the
// canonical `galleryFilter` Pinia store.
//
// Why: per constitution §VI.D, "active filters / search query / sort"
// are bookmarkable session state — they belong in the URL so anyone
// copying a link reproduces what they see.
//
// URL schema is intentionally identical to v1's `FilterDrawer/Base.vue`
// so links survive a v1↔v2 round-trip:
//
//   ?search=…
//   ?matched=true|false               (filterMatched)
//   ?filterFavorites=true|false       (filterFavorites)
//   ?filterDuplicates=true|false
//   ?filterPlayables=true|false
//   ?filterMissing=true|false
//   ?filterVerified=true|false
//   ?filterRA=true|false
//   ?platforms=1,2,3                  (selectedPlatforms IDs)
//   ?genres=a,b&genresLogic=any|all|none
//   ?franchises=…&franchisesLogic=…
//   ?collections=…&collectionsLogic=…
//   ?companies=…&companiesLogic=…
//   ?ageRatings=…&ageRatingsLogic=…
//   ?regions=…&regionsLogic=…
//   ?languages=…&languagesLogic=…
//   ?statuses=…&statusesLogic=…
//   ?playerCounts=…&playerCountsLogic=…
//   ?metadataProviders=…&metadataProvidersLogic=…
//   ?tags=…&tagsLogic=…
//
// Direction notes:
//   * URL → store fires on every `route.query` change (browser back /
//     forward / pasted URLs / programmatic route changes).
//   * Store → URL pushes via `router.replace` (no history per keystroke).
//     Writes are debounced so a flood of toggles produces one URL update.
//   * On mount we apply the URL value once so the gallery's setup reads
//     the correct store state before its first render.
//   * Platforms are looked up by ID against `platformsStore` — if the
//     store isn't populated yet, the lookup retries when platforms load.
import { debounce } from "lodash";
import { storeToRefs } from "pinia";
import { onMounted, watch } from "vue";
import {
  type LocationQueryRaw,
  type LocationQueryValue,
  useRoute,
  useRouter,
} from "vue-router";
import storeGalleryFilter, {
  type FilterLogicOperator,
} from "@/stores/galleryFilter";
import storePlatforms from "@/stores/platforms";

// Pure helpers — no Vue context. Easier to reason about and test if we
// ever want to.

function qStr(v: LocationQueryValue | LocationQueryValue[]): string | null {
  if (Array.isArray(v)) return v[0] ?? null;
  return typeof v === "string" && v.length > 0 ? v : null;
}

function qBool(v: LocationQueryValue | LocationQueryValue[]): boolean | null {
  const s = qStr(v);
  if (s === "true") return true;
  if (s === "false") return false;
  return null;
}

function qList(v: LocationQueryValue | LocationQueryValue[]): string[] {
  const s = qStr(v);
  if (!s) return [];
  return s.split(",").filter((p) => p.trim());
}

function qLogic(
  v: LocationQueryValue | LocationQueryValue[],
): FilterLogicOperator | null {
  const s = qStr(v);
  if (s === "any" || s === "all" || s === "none") return s;
  return null;
}

function eqStrArr(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false;
  return true;
}

export function useGalleryFilterUrl() {
  const route = useRoute();
  const router = useRouter();
  const filter = storeGalleryFilter();
  const platformsStore = storePlatforms();
  const platformsRefs = storeToRefs(platformsStore);
  const {
    searchTerm,
    filterMatched,
    filterFavorites,
    filterDuplicates,
    filterPlayables,
    filterMissing,
    filterVerified,
    filterRA,
    selectedPlatforms,
    selectedGenres,
    selectedFranchises,
    selectedCollections,
    selectedCompanies,
    selectedAgeRatings,
    selectedRegions,
    selectedLanguages,
    selectedPlayerCounts,
    selectedMetadataProviders,
    selectedTags,
    selectedStatuses,
    genresLogic,
    franchisesLogic,
    collectionsLogic,
    companiesLogic,
    ageRatingsLogic,
    regionsLogic,
    languagesLogic,
    playerCountsLogic,
    metadataProvidersLogic,
    tagsLogic,
    statusesLogic,
  } = storeToRefs(filter);

  // ── URL → store ──────────────────────────────────────────────
  // Hydrates the store with whatever the URL currently holds.
  // Comparisons skip writes when nothing changed, which keeps the
  // store→URL watcher below from echoing.
  function applyFromUrl() {
    const q = route.query;

    const url = {
      search: qStr(q.search),
      matched: qBool(q.matched),
      filterFavorites: qBool(q.filterFavorites),
      filterDuplicates: qBool(q.filterDuplicates),
      filterPlayables: qBool(q.filterPlayables),
      filterMissing: qBool(q.filterMissing),
      filterVerified: qBool(q.filterVerified),
      filterRA: qBool(q.filterRA),
      platformIds: qList(q.platforms)
        .map((s) => Number(s))
        .filter((n) => !Number.isNaN(n)),
      genres: qList(q.genres),
      genresLogic: qLogic(q.genresLogic),
      franchises: qList(q.franchises),
      franchisesLogic: qLogic(q.franchisesLogic),
      collections: qList(q.collections),
      collectionsLogic: qLogic(q.collectionsLogic),
      companies: qList(q.companies),
      companiesLogic: qLogic(q.companiesLogic),
      ageRatings: qList(q.ageRatings),
      ageRatingsLogic: qLogic(q.ageRatingsLogic),
      regions: qList(q.regions),
      regionsLogic: qLogic(q.regionsLogic),
      languages: qList(q.languages),
      languagesLogic: qLogic(q.languagesLogic),
      playerCounts: qList(q.playerCounts),
      playerCountsLogic: qLogic(q.playerCountsLogic),
      metadataProviders: qList(q.metadataProviders),
      metadataProvidersLogic: qLogic(q.metadataProvidersLogic),
      tags: qList(q.tags),
      tagsLogic: qLogic(q.tagsLogic),
      statuses: qList(q.statuses),
      statusesLogic: qLogic(q.statusesLogic),
    };

    if (url.search !== searchTerm.value) searchTerm.value = url.search;

    if (url.matched !== filterMatched.value) filterMatched.value = url.matched;
    if (url.filterFavorites !== filterFavorites.value)
      filterFavorites.value = url.filterFavorites;
    if (url.filterDuplicates !== filterDuplicates.value)
      filterDuplicates.value = url.filterDuplicates;
    if (url.filterPlayables !== filterPlayables.value)
      filterPlayables.value = url.filterPlayables;
    if (url.filterMissing !== filterMissing.value)
      filterMissing.value = url.filterMissing;
    if (url.filterVerified !== filterVerified.value)
      filterVerified.value = url.filterVerified;
    if (url.filterRA !== filterRA.value) filterRA.value = url.filterRA;

    // Platforms — lookup objects from IDs. If the platform store hasn't
    // hydrated yet, the watch below retries when it does.
    if (url.platformIds.length > 0) {
      const looked = url.platformIds
        .map((id) => platformsRefs.allPlatforms.value.find((p) => p.id === id))
        .filter((p): p is NonNullable<typeof p> => Boolean(p));
      const currentIds = selectedPlatforms.value.map((p) => p.id);
      if (!eqStrArr(currentIds.map(String), url.platformIds.map(String))) {
        // Only push the lookup result if we got every platform — partial
        // matches would silently drop filters the user expects to see.
        if (looked.length === url.platformIds.length) {
          filter.setSelectedFilterPlatforms(looked);
        }
      }
    } else if (selectedPlatforms.value.length > 0) {
      filter.setSelectedFilterPlatforms([]);
    }

    // Multi-select string arrays.
    if (!eqStrArr(url.genres, selectedGenres.value))
      filter.setSelectedFilterGenres(url.genres);
    if (url.genresLogic && url.genresLogic !== genresLogic.value)
      filter.setGenresLogic(url.genresLogic);

    if (!eqStrArr(url.franchises, selectedFranchises.value))
      filter.setSelectedFilterFranchises(url.franchises);
    if (url.franchisesLogic && url.franchisesLogic !== franchisesLogic.value)
      filter.setFranchisesLogic(url.franchisesLogic);

    if (!eqStrArr(url.collections, selectedCollections.value))
      filter.setSelectedFilterCollections(url.collections);
    if (url.collectionsLogic && url.collectionsLogic !== collectionsLogic.value)
      filter.setCollectionsLogic(url.collectionsLogic);

    if (!eqStrArr(url.companies, selectedCompanies.value))
      filter.setSelectedFilterCompanies(url.companies);
    if (url.companiesLogic && url.companiesLogic !== companiesLogic.value)
      filter.setCompaniesLogic(url.companiesLogic);

    if (!eqStrArr(url.ageRatings, selectedAgeRatings.value))
      filter.setSelectedFilterAgeRatings(url.ageRatings);
    if (url.ageRatingsLogic && url.ageRatingsLogic !== ageRatingsLogic.value)
      filter.setAgeRatingsLogic(url.ageRatingsLogic);

    if (!eqStrArr(url.regions, selectedRegions.value))
      filter.setSelectedFilterRegions(url.regions);
    if (url.regionsLogic && url.regionsLogic !== regionsLogic.value)
      filter.setRegionsLogic(url.regionsLogic);

    if (!eqStrArr(url.languages, selectedLanguages.value))
      filter.setSelectedFilterLanguages(url.languages);
    if (url.languagesLogic && url.languagesLogic !== languagesLogic.value)
      filter.setLanguagesLogic(url.languagesLogic);

    if (!eqStrArr(url.playerCounts, selectedPlayerCounts.value))
      filter.setSelectedFilterPlayerCounts(url.playerCounts);
    if (
      url.playerCountsLogic &&
      url.playerCountsLogic !== playerCountsLogic.value
    )
      filter.setPlayerCountsLogic(url.playerCountsLogic);

    if (!eqStrArr(url.metadataProviders, selectedMetadataProviders.value))
      filter.setSelectedFilterMetadataProviders(url.metadataProviders);
    if (
      url.metadataProvidersLogic &&
      url.metadataProvidersLogic !== metadataProvidersLogic.value
    )
      filter.setMetadataProvidersLogic(url.metadataProvidersLogic);

    if (!eqStrArr(url.tags, selectedTags.value))
      filter.setSelectedFilterTags(url.tags);
    if (url.tagsLogic && url.tagsLogic !== tagsLogic.value)
      filter.setTagsLogic(url.tagsLogic);

    if (!eqStrArr(url.statuses, selectedStatuses.value))
      filter.setSelectedFilterStatuses(url.statuses);
    if (url.statusesLogic && url.statusesLogic !== statusesLogic.value)
      filter.setStatusesLogic(url.statusesLogic);
  }

  // Apply once before the view's setup reads any of the refs.
  applyFromUrl();
  onMounted(applyFromUrl);

  // URL → store. Covers back/forward / addressbar paste / programmatic
  // route changes. Comparing against the current store value inside
  // `applyFromUrl` is what stops the loop with the store→URL watcher.
  watch(
    () => route.query,
    () => applyFromUrl(),
    { deep: true },
  );

  // Platforms can hydrate after the composable runs (gallery fetches
  // platforms in the background). Re-apply when the store gains items
  // so `?platforms=…` from a bookmark lands correctly.
  watch(
    () => platformsRefs.allPlatforms.value.length,
    () => applyFromUrl(),
  );

  // ── Store → URL ──────────────────────────────────────────────
  // Debounced so a flurry of changes (closing a chip wipes the whole
  // list one at a time) collapses into a single `router.replace`.
  function pushToUrl() {
    const desired: LocationQueryRaw = { ...route.query };

    function setOrDelete(key: string, value: string | null) {
      if (value === null || value === "") {
        delete desired[key];
      } else {
        desired[key] = value;
      }
    }
    function setBool(key: string, v: boolean | null) {
      setOrDelete(key, v === null ? null : String(v));
    }
    function setList(key: string, v: string[]) {
      setOrDelete(key, v.length > 0 ? v.join(",") : null);
    }

    setOrDelete("search", searchTerm.value);
    setBool("matched", filterMatched.value);
    setBool("filterFavorites", filterFavorites.value);
    setBool("filterDuplicates", filterDuplicates.value);
    setBool("filterPlayables", filterPlayables.value);
    setBool("filterMissing", filterMissing.value);
    setBool("filterVerified", filterVerified.value);
    setBool("filterRA", filterRA.value);

    setList(
      "platforms",
      selectedPlatforms.value.map((p) => String(p.id)),
    );

    setList("genres", selectedGenres.value);
    setOrDelete(
      "genresLogic",
      selectedGenres.value.length > 0 ? genresLogic.value : null,
    );
    setList("franchises", selectedFranchises.value);
    setOrDelete(
      "franchisesLogic",
      selectedFranchises.value.length > 0 ? franchisesLogic.value : null,
    );
    setList("collections", selectedCollections.value);
    setOrDelete(
      "collectionsLogic",
      selectedCollections.value.length > 0 ? collectionsLogic.value : null,
    );
    setList("companies", selectedCompanies.value);
    setOrDelete(
      "companiesLogic",
      selectedCompanies.value.length > 0 ? companiesLogic.value : null,
    );
    setList("ageRatings", selectedAgeRatings.value);
    setOrDelete(
      "ageRatingsLogic",
      selectedAgeRatings.value.length > 0 ? ageRatingsLogic.value : null,
    );
    setList("regions", selectedRegions.value);
    setOrDelete(
      "regionsLogic",
      selectedRegions.value.length > 0 ? regionsLogic.value : null,
    );
    setList("languages", selectedLanguages.value);
    setOrDelete(
      "languagesLogic",
      selectedLanguages.value.length > 0 ? languagesLogic.value : null,
    );
    setList("playerCounts", selectedPlayerCounts.value);
    setOrDelete(
      "playerCountsLogic",
      selectedPlayerCounts.value.length > 0 ? playerCountsLogic.value : null,
    );
    setList("metadataProviders", selectedMetadataProviders.value);
    setOrDelete(
      "metadataProvidersLogic",
      selectedMetadataProviders.value.length > 0
        ? metadataProvidersLogic.value
        : null,
    );
    setList("tags", selectedTags.value);
    setOrDelete(
      "tagsLogic",
      selectedTags.value.length > 0 ? tagsLogic.value : null,
    );
    setList("statuses", selectedStatuses.value);
    setOrDelete(
      "statusesLogic",
      selectedStatuses.value.length > 0 ? statusesLogic.value : null,
    );

    // Skip the push if nothing actually changed — keeps router from
    // emitting a route-update for an identical URL.
    const currentKeys = Object.keys(route.query).sort();
    const desiredKeys = Object.keys(desired).sort();
    if (
      currentKeys.length === desiredKeys.length &&
      currentKeys.every(
        (k, i) => k === desiredKeys[i] && route.query[k] === desired[k],
      )
    ) {
      return;
    }
    router.replace({ query: desired });
  }
  const pushDebounced = debounce(pushToUrl, 250);

  // Watch every store field that maps to a URL key. A single deep
  // watcher on the store would be cheaper but pulls in changes to
  // non-URL fields (drawer open state, filter ITEMS lists) that we
  // don't want to react to.
  watch(
    [
      searchTerm,
      filterMatched,
      filterFavorites,
      filterDuplicates,
      filterPlayables,
      filterMissing,
      filterVerified,
      filterRA,
      selectedPlatforms,
      selectedGenres,
      genresLogic,
      selectedFranchises,
      franchisesLogic,
      selectedCollections,
      collectionsLogic,
      selectedCompanies,
      companiesLogic,
      selectedAgeRatings,
      ageRatingsLogic,
      selectedRegions,
      regionsLogic,
      selectedLanguages,
      languagesLogic,
      selectedPlayerCounts,
      playerCountsLogic,
      selectedMetadataProviders,
      metadataProvidersLogic,
      selectedTags,
      tagsLogic,
      selectedStatuses,
      statusesLogic,
    ],
    () => pushDebounced(),
    { deep: true },
  );
}
