// Smart-collection filter criteria helpers — single source of truth for
// the v2 "create from filters" + "display read-only criteria" flows.
//
// v1 had this serialization logic duplicated inside
// `components/common/Collection/Dialog/CreateSmartCollection.vue` (build)
// and inside `Gallery/AppBar/Collection/SmartCollectionInfoDrawer.vue`
// (display). The two paths drifted: build wrote arrays + `*_logic`
// keys, display rendered raw `key: value` chips ignoring the logic
// pair. Centralising it here means create + display agree, and any
// future surface (search-bar promo, gallery banner) gets both
// behaviours for free.
//
// `SmartFilterCriteria` is the JSON shape the backend expects on
// `filter_criteria`. It mirrors v1's serialization exactly so existing
// smart collections continue to load.
import type { Composer } from "vue-i18n";
import type { Platform } from "@/stores/platforms";

export type FilterLogic = "any" | "all" | "none";

export interface SmartFilterCriteria {
  search_term?: string;
  platform_ids?: number[];
  matched?: boolean;
  favorite?: boolean;
  duplicate?: boolean;
  playable?: boolean;
  has_ra?: boolean;
  missing?: boolean;
  verified?: boolean;
  genres?: string[];
  genres_logic?: FilterLogic;
  franchises?: string[];
  franchises_logic?: FilterLogic;
  collections?: string[];
  collections_logic?: FilterLogic;
  companies?: string[];
  companies_logic?: FilterLogic;
  age_ratings?: string[];
  age_ratings_logic?: FilterLogic;
  regions?: string[];
  regions_logic?: FilterLogic;
  languages?: string[];
  languages_logic?: FilterLogic;
  player_counts?: string[];
  player_counts_logic?: FilterLogic;
  selected_status?: string[];
  statuses_logic?: FilterLogic;
}

// Subset of `storeGalleryFilter`'s state shape that we read from.
// Declaring it explicitly here keeps this module decoupled from the
// store (utils don't import Pinia stores).
export interface GalleryFilterSnapshot {
  searchTerm: string | null;
  filterMatched: boolean | null;
  filterFavorites: boolean | null;
  filterDuplicates: boolean | null;
  filterPlayables: boolean | null;
  filterRA: boolean | null;
  filterMissing: boolean | null;
  filterVerified: boolean | null;
  selectedPlatforms: Platform[];
  selectedGenres: string[];
  genresLogic: FilterLogic;
  selectedFranchises: string[];
  franchisesLogic: FilterLogic;
  selectedCollections: string[];
  collectionsLogic: FilterLogic;
  selectedCompanies: string[];
  companiesLogic: FilterLogic;
  selectedAgeRatings: string[];
  ageRatingsLogic: FilterLogic;
  selectedRegions: string[];
  regionsLogic: FilterLogic;
  selectedLanguages: string[];
  languagesLogic: FilterLogic;
  selectedPlayerCounts: string[];
  playerCountsLogic: FilterLogic;
  selectedStatuses: string[];
  statusesLogic: FilterLogic;
}

/**
 * Serialize the active gallery filter state into the JSON shape the
 * backend stores on `smart_collection.filter_criteria`.
 *
 * The fallback `currentPlatform` argument covers the Platform.vue case:
 * the user is on `/platform/:slug` so the platform filter isn't a
 * multi-select selection but the route context — we still want it
 * captured.
 */
export function buildSmartFilterCriteria(
  snap: GalleryFilterSnapshot,
  currentPlatform?: Platform | null,
): SmartFilterCriteria {
  const out: SmartFilterCriteria = {};

  if (snap.searchTerm) out.search_term = snap.searchTerm;

  if (snap.selectedPlatforms.length > 0) {
    out.platform_ids = snap.selectedPlatforms.map((p) => p.id);
  } else if (currentPlatform) {
    out.platform_ids = [currentPlatform.id];
  }

  if (snap.filterMatched) out.matched = true;
  if (snap.filterFavorites) out.favorite = true;
  if (snap.filterDuplicates) out.duplicate = true;
  if (snap.filterPlayables) out.playable = true;
  if (snap.filterRA) out.has_ra = true;
  if (snap.filterMissing) out.missing = true;
  if (snap.filterVerified) out.verified = true;

  if (snap.selectedGenres.length > 0) {
    out.genres = snap.selectedGenres;
    out.genres_logic = snap.genresLogic;
  }
  if (snap.selectedFranchises.length > 0) {
    out.franchises = snap.selectedFranchises;
    out.franchises_logic = snap.franchisesLogic;
  }
  if (snap.selectedCollections.length > 0) {
    out.collections = snap.selectedCollections;
    out.collections_logic = snap.collectionsLogic;
  }
  if (snap.selectedCompanies.length > 0) {
    out.companies = snap.selectedCompanies;
    out.companies_logic = snap.companiesLogic;
  }
  if (snap.selectedAgeRatings.length > 0) {
    out.age_ratings = snap.selectedAgeRatings;
    out.age_ratings_logic = snap.ageRatingsLogic;
  }
  if (snap.selectedRegions.length > 0) {
    out.regions = snap.selectedRegions;
    out.regions_logic = snap.regionsLogic;
  }
  if (snap.selectedLanguages.length > 0) {
    out.languages = snap.selectedLanguages;
    out.languages_logic = snap.languagesLogic;
  }
  if (snap.selectedPlayerCounts.length > 0) {
    out.player_counts = snap.selectedPlayerCounts;
    out.player_counts_logic = snap.playerCountsLogic;
  }
  if (snap.selectedStatuses.length > 0) {
    out.selected_status = snap.selectedStatuses;
    out.statuses_logic = snap.statusesLogic;
  }

  return out;
}

/** True when at least one filter is set — drives the "no filters" warning. */
export function hasAnySmartFilterCriteria(c: SmartFilterCriteria): boolean {
  return Object.keys(c).length > 0;
}

/** One row of the human-readable summary. */
export interface SmartCriteriaSummaryItem {
  key: string;
  icon: string;
  label: string;
  /** Either a list of value chips or a single boolean-style label. */
  values?: string[];
  logic?: FilterLogic;
}

// Maps each storage key to its (icon, label, kind).
//   - "list":   array of strings → values chip list
//   - "bool":   true flag → no values, label says it all
//   - "search": single string → values = [searchTerm]
//   - "platforms": ids → values = mapper(id)
type FieldKind = "list" | "bool" | "search" | "platforms";
interface FieldSpec {
  storage: keyof SmartFilterCriteria;
  logicStorage?: keyof SmartFilterCriteria;
  icon: string;
  labelKey: string;
  defaultLabel: string;
  kind: FieldKind;
}

// Order = visual order of the summary. Stable across renders.
const FIELDS: FieldSpec[] = [
  {
    storage: "search_term",
    icon: "mdi-magnify",
    labelKey: "common.search",
    defaultLabel: "Search",
    kind: "search",
  },
  {
    storage: "platform_ids",
    icon: "mdi-monitor",
    labelKey: "common.platforms",
    defaultLabel: "Platforms",
    kind: "platforms",
  },
  {
    storage: "favorite",
    icon: "mdi-star",
    labelKey: "platform.show-favorites",
    defaultLabel: "Show favourites",
    kind: "bool",
  },
  {
    storage: "matched",
    icon: "mdi-check-decagram",
    labelKey: "platform.show-matched",
    defaultLabel: "Show matched",
    kind: "bool",
  },
  {
    storage: "duplicate",
    icon: "mdi-content-duplicate",
    labelKey: "platform.show-duplicates",
    defaultLabel: "Show duplicates",
    kind: "bool",
  },
  {
    storage: "playable",
    icon: "mdi-gamepad-variant-outline",
    labelKey: "platform.show-playables",
    defaultLabel: "Show playables",
    kind: "bool",
  },
  {
    storage: "has_ra",
    icon: "mdi-trophy-outline",
    labelKey: "platform.show-ra",
    defaultLabel: "Show RetroAchievements",
    kind: "bool",
  },
  {
    storage: "missing",
    icon: "mdi-file-alert-outline",
    labelKey: "platform.show-missing",
    defaultLabel: "Show missing",
    kind: "bool",
  },
  {
    storage: "verified",
    icon: "mdi-shield-check-outline",
    labelKey: "platform.show-verified",
    defaultLabel: "Show verified",
    kind: "bool",
  },
  {
    storage: "genres",
    logicStorage: "genres_logic",
    icon: "mdi-shape-outline",
    labelKey: "platform.genre",
    defaultLabel: "Genres",
    kind: "list",
  },
  {
    storage: "franchises",
    logicStorage: "franchises_logic",
    icon: "mdi-source-branch",
    labelKey: "platform.franchise",
    defaultLabel: "Franchises",
    kind: "list",
  },
  {
    storage: "collections",
    logicStorage: "collections_logic",
    icon: "mdi-bookmark-multiple-outline",
    labelKey: "platform.collection",
    defaultLabel: "Collections",
    kind: "list",
  },
  {
    storage: "companies",
    logicStorage: "companies_logic",
    icon: "mdi-domain",
    labelKey: "platform.company",
    defaultLabel: "Companies",
    kind: "list",
  },
  {
    storage: "age_ratings",
    logicStorage: "age_ratings_logic",
    icon: "mdi-account-child-outline",
    labelKey: "platform.age-rating",
    defaultLabel: "Age ratings",
    kind: "list",
  },
  {
    storage: "regions",
    logicStorage: "regions_logic",
    icon: "mdi-earth",
    labelKey: "platform.region",
    defaultLabel: "Regions",
    kind: "list",
  },
  {
    storage: "languages",
    logicStorage: "languages_logic",
    icon: "mdi-translate",
    labelKey: "platform.language",
    defaultLabel: "Languages",
    kind: "list",
  },
  {
    storage: "player_counts",
    logicStorage: "player_counts_logic",
    icon: "mdi-account-multiple-outline",
    labelKey: "platform.player-count",
    defaultLabel: "Player counts",
    kind: "list",
  },
  {
    storage: "selected_status",
    logicStorage: "statuses_logic",
    icon: "mdi-flag-outline",
    labelKey: "platform.status",
    defaultLabel: "Statuses",
    kind: "list",
  },
];

/**
 * Translate `filter_criteria` into a structured list of rows the UI can
 * render. Callers pass:
 *   - `t`     — vue-i18n composer for labels.
 *   - `platformLookup` — id → display name (so the chips read "SNES"
 *     instead of `{1}`). Pass a no-op `() => null` when platforms aren't
 *     loaded; the row falls back to the numeric id.
 */
export function summarizeSmartFilterCriteria(
  criteria: SmartFilterCriteria,
  t: Composer["t"],
  platformLookup?: (id: number) => string | null,
): SmartCriteriaSummaryItem[] {
  const out: SmartCriteriaSummaryItem[] = [];
  for (const f of FIELDS) {
    const raw = criteria[f.storage];
    const label = t(f.labelKey, f.defaultLabel);

    if (f.kind === "search") {
      if (typeof raw === "string" && raw.length > 0) {
        out.push({ key: f.storage, icon: f.icon, label, values: [raw] });
      }
    } else if (f.kind === "bool") {
      if (raw === true) {
        out.push({ key: f.storage, icon: f.icon, label });
      }
    } else if (f.kind === "platforms") {
      if (Array.isArray(raw) && raw.length > 0) {
        const values = (raw as number[]).map(
          (id) => platformLookup?.(id) ?? `#${id}`,
        );
        out.push({ key: f.storage, icon: f.icon, label, values });
      }
    } else if (f.kind === "list") {
      if (Array.isArray(raw) && raw.length > 0) {
        const logic =
          f.logicStorage !== undefined
            ? (criteria[f.logicStorage] as FilterLogic | undefined)
            : undefined;
        out.push({
          key: f.storage,
          icon: f.icon,
          label,
          values: raw as string[],
          logic,
        });
      }
    }
  }
  return out;
}
