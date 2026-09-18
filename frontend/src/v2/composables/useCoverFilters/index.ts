// useCoverFilters: client-side filtering + sorting over the cover grid
// (SteamGridDB and Steam) and the per-provider cover row shown in
// SearchCoverDialog.
//
// The backend returns every content variant (NSFW / humor / epilepsy)
// with its per-cover metadata in one call, so every control here just
// narrows the already-loaded result set.
// The dialog owns the search flow and passes the raw `covers` /
// `providerCovers` refs in; this composable owns the filter state
// and every derived view of those two lists.
import { computed, ref, watch, type Ref } from "vue";
import { useI18n } from "vue-i18n";
import type { CoverResource, SearchCoverSchema } from "@/__generated__";
import type { MatchedSource } from "@/v2/components/MatchRom/types";

export type CoverType = "all" | "static" | "animated";
export type SortMode = "relevance" | "votes";
export type CoverProvider = SearchCoverSchema["provider"];

const ALL_PROVIDERS_ACTIVE: Record<CoverProvider, boolean> = {
  sgdb: true,
  steam: true,
};

// SGDB serves styles as raw slugs; map the known set to readable labels
// and fall back to the slug for anything new SGDB adds later.
const STYLE_LABEL_KEYS: Record<string, string> = {
  alternate: "rom.cover-style-alternate",
  blurred: "rom.cover-style-blurred",
  white_logo: "rom.cover-style-white-logo",
  material: "rom.cover-style-material",
  no_logo: "rom.cover-style-no-logo",
};

export function useCoverFilters(
  covers: Ref<SearchCoverSchema[]>,
  providerCovers: Ref<MatchedSource[]>,
) {
  const { t } = useI18n();

  const coverType = ref<CoverType>("all");
  const resolutionFilter = ref("all");
  const styleFilter = ref("all");
  const uploaderFilter = ref("all");
  const uploaderSearch = ref("");
  const showNsfw = ref(false);
  const showHumor = ref(true);
  const showEpilepsy = ref(true);
  const sortMode = ref<SortMode>("relevance");
  const activeProviders = ref<Record<CoverProvider, boolean>>({
    ...ALL_PROVIDERS_ACTIVE,
  });

  function toggleProvider(provider: CoverProvider) {
    activeProviders.value[provider] = !activeProviders.value[provider];
  }

  // These options come from the loaded results, so a pick from an earlier
  // search would keep hiding covers once the new results drop its select.
  function resetResultFilters() {
    resolutionFilter.value = "all";
    styleFilter.value = "all";
    uploaderFilter.value = "all";
    uploaderSearch.value = "";
  }
  watch(covers, resetResultFilters);

  function resetFilters() {
    activeProviders.value = { ...ALL_PROVIDERS_ACTIVE };
    coverType.value = "all";
    resetResultFilters();
    showNsfw.value = false;
    showHumor.value = true;
    showEpilepsy.value = true;
    sortMode.value = "relevance";
  }

  function styleLabel(style: string): string {
    const key = STYLE_LABEL_KEYS[style];
    return key ? t(key) : style;
  }

  const coverTypeItems = computed(() => [
    { title: t("rom.cover-type-all"), value: "all" },
    { title: t("rom.cover-type-static"), value: "static" },
    { title: t("rom.cover-type-animated"), value: "animated" },
  ]);

  // Every grid resource across all matched games, whichever provider.
  const allResources = computed(() => covers.value.flatMap((g) => g.resources));
  // The style, uploader, votes and content flags are SteamGridDB's own, so
  // their controls only appear when SteamGridDB answered.
  const hasSgdbCovers = computed(() =>
    covers.value.some((g) => g.provider === "sgdb" && g.resources.length > 0),
  );

  // Filters moved off their `resetFilters` defaults. The content switches
  // only render when SteamGridDB answered, so only then do they count.
  const activeFilterCount = computed(() => {
    const changed = [
      coverType.value !== "all",
      resolutionFilter.value !== "all",
      styleFilter.value !== "all",
      uploaderFilter.value !== "all",
    ];
    if (hasSgdbCovers.value) {
      changed.push(showNsfw.value, !showHumor.value, !showEpilepsy.value);
    }
    return changed.filter(Boolean).length;
  });

  const resolutionValues = computed(() => {
    const set = new Set<string>();
    for (const r of allResources.value) {
      if (r.width > 0 && r.height > 0) set.add(`${r.width}x${r.height}`);
    }
    // Largest area first — the highest-res covers are what users usually want.
    return [...set].sort((a, b) => {
      const [aw, ah] = a.split("x").map(Number);
      const [bw, bh] = b.split("x").map(Number);
      return bw * bh - aw * ah || bw - aw;
    });
  });
  const resolutionItems = computed(() => [
    { title: t("rom.cover-filter-resolution-all"), value: "all" },
    ...resolutionValues.value.map((v) => ({
      title: v.replace("x", "×"),
      value: v,
    })),
  ]);

  const styleValues = computed(() => {
    const set = new Set<string>();
    for (const r of allResources.value) if (r.style) set.add(r.style);
    return [...set].sort();
  });
  const styleItems = computed(() => [
    { title: t("rom.cover-filter-style-all"), value: "all" },
    ...styleValues.value.map((v) => ({ title: styleLabel(v), value: v })),
  ]);

  const uploaderValues = computed(() => {
    const set = new Set<string>();
    for (const r of allResources.value) if (r.author) set.add(r.author);
    return [...set].sort((a, b) => a.localeCompare(b));
  });
  const uploaderItems = computed(() => [
    { title: t("rom.cover-filter-uploader-all"), value: "all" },
    ...uploaderValues.value.map((v) => ({ title: v, value: v })),
  ]);

  // Does a single grid resource pass all active filters?
  function matchesFilters(r: CoverResource): boolean {
    if (coverType.value !== "all" && r.type !== coverType.value) return false;
    if (
      resolutionFilter.value !== "all" &&
      `${r.width}x${r.height}` !== resolutionFilter.value
    )
      return false;
    if (styleFilter.value !== "all" && r.style !== styleFilter.value)
      return false;
    if (uploaderFilter.value !== "all" && r.author !== uploaderFilter.value)
      return false;
    // Content flags are opt-in: a flagged cover shows only when its toggle is on.
    if (r.nsfw && !showNsfw.value) return false;
    if (r.humor && !showHumor.value) return false;
    if (r.epilepsy && !showEpilepsy.value) return false;
    return true;
  }

  // Filter (and optionally re-sort by votes) the fetched list without
  // re-hitting the API. SGDB sometimes returns a game entry with an empty
  // `resources` array — or one emptied by the active filters — so we drop
  // those so the accordion doesn't render an empty section.
  const filteredCovers = computed<SearchCoverSchema[]>(() => {
    return covers.value
      .filter((game) => activeProviders.value[game.provider])
      .map((game) => {
        const resources = game.resources.filter(matchesFilters);
        if (sortMode.value === "votes") {
          resources.sort((a, b) => b.score - a.score);
        }
        return { ...game, resources };
      })
      .filter((g) => g.resources.length > 0);
  });

  const hasGridCovers = computed(() => allResources.value.length > 0);
  const hasProviderCovers = computed(() => providerCovers.value.length > 0);
  // Provider covers (IGDB / Moby / SS / …) are static artwork only — they
  // don't carry an animated variant, so hide them when filtering to
  // "animated".
  const visibleProviderCovers = computed<MatchedSource[]>(() =>
    coverType.value === "animated" ? [] : providerCovers.value,
  );

  const hasGridResults = computed(() => filteredCovers.value.length > 0);
  const showProviderCovers = computed(
    () => visibleProviderCovers.value.length > 0,
  );
  // Raw results present (pre-filter) — drives whether the filter bar shows,
  // so filtering everything out never hides the controls needed to undo it.
  const hasRawResults = computed(
    () => hasGridCovers.value || hasProviderCovers.value,
  );
  const hasResults = computed(
    () => hasGridResults.value || showProviderCovers.value,
  );

  return {
    // Filter state (v-model bound in the dialog)
    coverType,
    resolutionFilter,
    styleFilter,
    uploaderFilter,
    uploaderSearch,
    showNsfw,
    showHumor,
    showEpilepsy,
    sortMode,
    activeProviders,
    toggleProvider,
    resetFilters,
    activeFilterCount,
    // Select option lists + their raw value sets (drive `v-if` on selects)
    coverTypeItems,
    resolutionItems,
    resolutionValues,
    styleItems,
    styleValues,
    uploaderItems,
    uploaderValues,
    // Derived views of the two source lists
    filteredCovers,
    visibleProviderCovers,
    hasSgdbCovers,
    hasGridResults,
    showProviderCovers,
    hasRawResults,
    hasResults,
  };
}
