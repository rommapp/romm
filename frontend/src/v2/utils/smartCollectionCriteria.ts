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
  /** Captures "inside a regular collection" when the smart collection was
   *  created — so applying extra filters inside Castlevania produces a
   *  smart collection scoped to Castlevania, not the whole library. */
  collection_id?: number;
  virtual_collection_id?: string;
  smart_collection_id?: number;
  matched?: boolean;
  favorite?: boolean;
  duplicate?: boolean;
  playable?: boolean;
  has_ra?: boolean;
  has_soundtrack?: boolean;
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
  publishers?: string[];
  publishers_logic?: FilterLogic;
  developers?: string[];
  developers_logic?: FilterLogic;
  age_ratings?: string[];
  age_ratings_logic?: FilterLogic;
  regions?: string[];
  regions_logic?: FilterLogic;
  languages?: string[];
  languages_logic?: FilterLogic;
  player_counts?: string[];
  player_counts_logic?: FilterLogic;
  metadata_providers?: string[];
  metadata_providers_logic?: FilterLogic;
  tags?: string[];
  tags_logic?: FilterLogic;
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
  filterSoundtrack: boolean | null;
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
  selectedPublishers: string[];
  publishersLogic: FilterLogic;
  selectedDevelopers: string[];
  developersLogic: FilterLogic;
  selectedAgeRatings: string[];
  ageRatingsLogic: FilterLogic;
  selectedRegions: string[];
  regionsLogic: FilterLogic;
  selectedLanguages: string[];
  languagesLogic: FilterLogic;
  selectedPlayerCounts: string[];
  playerCountsLogic: FilterLogic;
  selectedMetadataProviders: string[];
  metadataProvidersLogic: FilterLogic;
  selectedTags: string[];
  tagsLogic: FilterLogic;
  selectedStatuses: string[];
  statusesLogic: FilterLogic;
}

/**
 * Optional route-level context the user is currently navigating in.
 * These aren't toggles in the filter drawer — they come from the URL
 * (`/platform/:slug`, `/collection/:id`, …) — but the smart collection
 * still needs to capture them so it stays scoped to that view.
 */
export interface GalleryContext {
  currentPlatform?: Platform | null;
  currentCollectionId?: number | null;
  currentVirtualCollectionId?: string | null;
  currentSmartCollectionId?: number | null;
}

/**
 * Serialize the active gallery filter state into the JSON shape the
 * backend stores on `smart_collection.filter_criteria`.
 *
 * `context` captures the route the user is on (platform / collection /
 * virtual / smart) so a smart collection created inside Castlevania
 * stays scoped to Castlevania, not the whole library.
 */
export function buildSmartFilterCriteria(
  snap: GalleryFilterSnapshot,
  context: GalleryContext = {},
): SmartFilterCriteria {
  const out: SmartFilterCriteria = {};

  if (snap.searchTerm) out.search_term = snap.searchTerm;

  if (snap.selectedPlatforms.length > 0) {
    out.platform_ids = snap.selectedPlatforms.map((p) => p.id);
  } else if (context.currentPlatform) {
    out.platform_ids = [context.currentPlatform.id];
  }

  if (context.currentCollectionId != null) {
    out.collection_id = context.currentCollectionId;
  }
  if (context.currentVirtualCollectionId != null) {
    out.virtual_collection_id = context.currentVirtualCollectionId;
  }
  if (context.currentSmartCollectionId != null) {
    out.smart_collection_id = context.currentSmartCollectionId;
  }

  if (snap.filterMatched) out.matched = true;
  if (snap.filterFavorites) out.favorite = true;
  if (snap.filterDuplicates) out.duplicate = true;
  if (snap.filterPlayables) out.playable = true;
  if (snap.filterRA) out.has_ra = true;
  if (snap.filterSoundtrack) out.has_soundtrack = true;
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
  if (snap.selectedPublishers.length > 0) {
    out.publishers = snap.selectedPublishers;
    out.publishers_logic = snap.publishersLogic;
  }
  if (snap.selectedDevelopers.length > 0) {
    out.developers = snap.selectedDevelopers;
    out.developers_logic = snap.developersLogic;
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
  if (snap.selectedMetadataProviders.length > 0) {
    out.metadata_providers = snap.selectedMetadataProviders;
    out.metadata_providers_logic = snap.metadataProvidersLogic;
  }
  if (snap.selectedTags.length > 0) {
    out.tags = snap.selectedTags;
    out.tags_logic = snap.tagsLogic;
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
//   - "list":     array of strings → values chip list
//   - "bool":     true flag → no values, label says it all
//   - "search":   single string → values = [searchTerm]
//   - "platforms": ids → values = mapper(id)
//   - "collection":      single id (number) → values = [mapper(id)]
//   - "virtual-collection": single id (string) → values = [mapper(id)]
//   - "smart-collection":   single id (number) → values = [mapper(id)]
type FieldKind =
  | "list"
  | "bool"
  | "search"
  | "platforms"
  | "collection"
  | "virtual-collection"
  | "smart-collection";
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
    storage: "collection_id",
    icon: "mdi-bookmark-outline",
    labelKey: "platform.collection",
    defaultLabel: "Collection",
    kind: "collection",
  },
  {
    storage: "virtual_collection_id",
    icon: "mdi-bookmark-box",
    labelKey: "common.virtual-collection",
    defaultLabel: "Virtual collection",
    kind: "virtual-collection",
  },
  {
    storage: "smart_collection_id",
    icon: "mdi-bookmark-multiple-outline",
    labelKey: "common.smart-collection",
    defaultLabel: "Smart collection",
    kind: "smart-collection",
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
    defaultLabel: "Show versions",
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
    storage: "has_soundtrack",
    icon: "mdi-music-note",
    labelKey: "platform.has-soundtrack",
    defaultLabel: "Has soundtrack",
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
    storage: "publishers",
    logicStorage: "publishers_logic",
    icon: "mdi-bank-outline",
    labelKey: "platform.publisher",
    defaultLabel: "Publishers",
    kind: "list",
  },
  {
    storage: "developers",
    logicStorage: "developers_logic",
    icon: "mdi-code-tags",
    labelKey: "platform.developer",
    defaultLabel: "Developers",
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
    storage: "metadata_providers",
    logicStorage: "metadata_providers_logic",
    icon: "mdi-database-outline",
    labelKey: "platform.metadata-provider",
    defaultLabel: "Metadata providers",
    kind: "list",
  },
  {
    storage: "tags",
    logicStorage: "tags_logic",
    icon: "mdi-tag-outline",
    labelKey: "platform.tag",
    defaultLabel: "Tags",
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

export interface SummaryLookups {
  /** Platform id → display name. */
  platform?: (id: number) => string | null;
  /** Regular collection id → display name. */
  collection?: (id: number) => string | null;
  /** Virtual collection id → display name. */
  virtualCollection?: (id: string) => string | null;
  /** Smart collection id → display name. */
  smartCollection?: (id: number) => string | null;
}

/**
 * Translate `filter_criteria` into a structured list of rows the UI can
 * render. Callers pass:
 *   - `t`       — vue-i18n composer for labels.
 *   - `lookups` — id → display name resolvers for platforms / collections.
 *     Each is optional; rows fall back to a `#id` chip when missing.
 *
 * The legacy `(id) => string | null` shape (platforms-only) stays
 * supported so older call sites don't break before migration.
 */
export function summarizeSmartFilterCriteria(
  criteria: SmartFilterCriteria,
  t: Composer["t"],
  lookups?: SummaryLookups | ((id: number) => string | null),
): SmartCriteriaSummaryItem[] {
  const resolved: SummaryLookups =
    typeof lookups === "function" ? { platform: lookups } : (lookups ?? {});
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
          (id) => resolved.platform?.(id) ?? `#${id}`,
        );
        out.push({ key: f.storage, icon: f.icon, label, values });
      }
    } else if (f.kind === "collection") {
      if (typeof raw === "number") {
        out.push({
          key: f.storage,
          icon: f.icon,
          label,
          values: [resolved.collection?.(raw) ?? `#${raw}`],
        });
      }
    } else if (f.kind === "virtual-collection") {
      if (typeof raw === "string" && raw.length > 0) {
        out.push({
          key: f.storage,
          icon: f.icon,
          label,
          values: [resolved.virtualCollection?.(raw) ?? raw],
        });
      }
    } else if (f.kind === "smart-collection") {
      if (typeof raw === "number") {
        out.push({
          key: f.storage,
          icon: f.icon,
          label,
          values: [resolved.smartCollection?.(raw) ?? `#${raw}`],
        });
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
