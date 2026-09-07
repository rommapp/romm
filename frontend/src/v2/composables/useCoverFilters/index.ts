// useCoverFilters — client-side filtering + sorting over the SGDB cover
// grid and the per-provider cover row shown in SearchCoverDialog.
//
// The backend returns every content variant (NSFW / humor / epilepsy)
// with its per-cover metadata in one call, so every control here just
// narrows the already-loaded result set.
// The dialog owns the search flow and passes the raw `covers` /
// `providerCovers` refs in; this composable owns the filter state
// and every derived view of those two lists.
import { computed, ref, type Ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SearchCoverSchema, SGDBResource } from "@/__generated__";
import type { MatchedSource } from "@/v2/components/MatchRom/types";

export type CoverType = "all" | "static" | "animated";
export type SortMode = "relevance" | "votes";

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

  function resetFilters() {
    coverType.value = "all";
    resolutionFilter.value = "all";
    styleFilter.value = "all";
    uploaderFilter.value = "all";
    uploaderSearch.value = "";
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

  // Every SGDB resource across all matched games
  const allResources = computed(() => covers.value.flatMap((g) => g.resources));

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

  // Does a single SGDB resource pass all active filters?
  function matchesFilters(r: SGDBResource): boolean {
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

  // Filter (and optionally re-sort by votes) the fetched SGDB list without
  // re-hitting the API. SGDB sometimes returns a game entry with an empty
  // `resources` array — or one emptied by the active filters — so we drop
  // those so the accordion doesn't render an empty section.
  const filteredCovers = computed<SearchCoverSchema[]>(() => {
    return covers.value
      .map((game) => {
        const resources = game.resources.filter(matchesFilters);
        if (sortMode.value === "votes") {
          resources.sort((a, b) => b.score - a.score);
        }
        return { ...game, resources };
      })
      .filter((g) => g.resources.length > 0);
  });

  const hasSgdbCovers = computed(() => allResources.value.length > 0);
  const hasProviderCovers = computed(() => providerCovers.value.length > 0);
  // Provider covers (IGDB / Moby / SS / …) are static artwork only — they
  // don't carry an animated variant, so hide them when filtering to
  // "animated".
  const visibleProviderCovers = computed<MatchedSource[]>(() =>
    coverType.value === "animated" ? [] : providerCovers.value,
  );

  const hasSgdbResults = computed(() => filteredCovers.value.length > 0);
  const showProviderCovers = computed(
    () => visibleProviderCovers.value.length > 0,
  );
  // Raw results present (pre-filter) — drives whether the filter bar shows,
  // so filtering everything out never hides the controls needed to undo it.
  const hasRawResults = computed(
    () => hasSgdbCovers.value || hasProviderCovers.value,
  );
  const hasResults = computed(
    () => hasSgdbResults.value || showProviderCovers.value,
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
    resetFilters,
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
    hasSgdbResults,
    showProviderCovers,
    hasRawResults,
    hasResults,
  };
}
