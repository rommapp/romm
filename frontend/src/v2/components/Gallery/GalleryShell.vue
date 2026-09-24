<script setup lang="ts">
// GalleryShell — shared layout for Platform / Search / Collection.
//
// Three structural sections, top to bottom, all sharing one scrollbar:
//   1. HEADER: view-supplied via `#header` slot. Whatever the view
//                wants there: an InfoPanel with platform / collection
//                metadata, a plain PageHeader for Search, etc.
//   2. TOOLBAR: search input + group/layout/dock controls. Sticky right
//                below the top bar; once pinned it shares one glass surface
//                with the top bar, so cards blur behind both.
//   3. GRID / TABLE: the row-virtualised content (cards in grid mode,
//                div-based rows in list mode — same shell scroller, same
//                AlphaStrip wiring; the list column header lives in the
//                prepend, sticky below the toolbar).
//
// Cross-view behaviour owned by the shell: the virtualizer, sticky
// glass toolbar + sticky list column header, AlphaStrip,
// grid per-row dwell-debounced prefetch, scroll restoration,
// search-input debounce, URL filter sync. Each view supplies its
// header and its own resource-load flow. List rows own their per-row
// fetch lifecycle internally (mount = entered overscan window).
import {
  RDivider,
  REmptyState,
  RLetterHeading,
  RVirtualScroller,
} from "@v2/lib";
import { useIntersectionObserver } from "@vueuse/core";
import { storeToRefs } from "pinia";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  watchEffect,
} from "vue";
import { useI18n } from "vue-i18n";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from "vue-router";
import { useUISettings } from "@/composables/useUISettings";
import storeGalleryFilter from "@/stores/galleryFilter";
import AlphaJumpMenu from "@/v2/components/Gallery/AlphaJumpMenu.vue";
import AlphaStrip from "@/v2/components/Gallery/AlphaStrip.vue";
import FilterDrawer from "@/v2/components/Gallery/FilterDrawer.vue";
import GalleryToolbar from "@/v2/components/Gallery/GalleryToolbar.vue";
import GameListHeader from "@/v2/components/Gallery/GameListHeader.vue";
import GameListRow from "@/v2/components/Gallery/GameListRow.vue";
import GameListSkeletonRow from "@/v2/components/Gallery/GameListSkeletonRow.vue";
import SelectionBar from "@/v2/components/Gallery/SelectionBar.vue";
import {
  getListMinWidth,
  getSortOptions,
  isListSortKey,
  LIST_HEADER_HEIGHT_PX,
  LIST_ROW_PAD_X_PX,
  type ListSortKey,
} from "@/v2/components/Gallery/listColumns";
import { GameCard, GameCardSkeleton } from "@/v2/components/GameCard";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { coverRatio, isBoxartStyle } from "@/v2/composables/useCoverArt";
import { useDebugMode } from "@/v2/composables/useDebugMode";
import { useGalleryCoverRatios } from "@/v2/composables/useGalleryCoverRatios";
import { useGalleryFilterUrl } from "@/v2/composables/useGalleryFilterUrl";
import { useGalleryMode } from "@/v2/composables/useGalleryMode";
import { useGalleryOrderUrl } from "@/v2/composables/useGalleryOrderUrl";
import { useGallerySelectAll } from "@/v2/composables/useGallerySelectAll";
import { useGallerySelectionInput } from "@/v2/composables/useGallerySelectionInput";
import { useGalleryViewModeUrl } from "@/v2/composables/useGalleryViewModeUrl";
import {
  useGalleryVirtualItems,
  type GalleryItem,
} from "@/v2/composables/useGalleryVirtualItems";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useListExpansion } from "@/v2/composables/useListExpansion";
import { usePinnedToolbar } from "@/v2/composables/usePinnedToolbar";
import { useResponsiveColumns } from "@/v2/composables/useResponsiveColumns";
import { useVirtualScrollDebug } from "@/v2/composables/useVirtualScrollDebug";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms, {
  orderSupportsLetters,
} from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import storeScrollRestoration from "@/v2/stores/scrollRestoration";
import { layout as layoutTokens, space } from "@/v2/tokens";

interface Props {
  /** Whether the header slot has content to render. False suppresses
   * the header (the prepend band collapses; toolbar pins immediately). */
  hasHeader: boolean;
  /** Toolbar's search-input placeholder. */
  searchPlaceholder: string;
  /** Focus the toolbar's search field on mount. */
  autofocusSearch?: boolean;
  /** Empty-state message shown when the gallery resolves with zero items. */
  emptyMessage: string;
  /** Empty-state icon, shared with not-found mode. */
  emptyIcon?: string;
  /** "Not found" mode — replaces all body items with a single empty row. */
  notFound?: boolean;
  /** Override the empty-state message in not-found mode. */
  notFoundMessage?: string;
  /** Whether GameCards should display the platform badge corner (Search /
   * Collection: yes; Platform: no — the cards already share a platform). */
  showPlatformBadge?: boolean;
  /** Skeleton row count painted while the very first window is loading. */
  skeletonRowCount?: number;
  /** Surface the platforms multi-select inside the filter drawer.
   *  False for single-platform views (Platform.vue) where the platform
   *  context is fixed; true for cross-platform views (Collection, Search). */
  showPlatformsInFilter?: boolean;
  /** Include the `platform` column in list mode. False on Platform.vue
   * (every row shares the same platform); true on cross-platform views
   * (Search, Collection, Missing games) where the column carries info. */
  showPlatformColumn?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  autofocusSearch: false,
  emptyIcon: "mdi-gamepad-variant-outline",
  notFound: false,
  notFoundMessage: undefined,
  showPlatformBadge: true,
  skeletonRowCount: 4,
  showPlatformsInFilter: true,
  showPlatformColumn: true,
});

defineSlots<{
  /** View-specific header (InfoPanel / PageHeader / etc). Rendered in
   * the scroller's `#prepend` slot — scrolls naturally with the rest
   * of the content. Must NOT carry a divider of its own; the shell
   * paints the single divider at the bottom of the prepend band. */
  header(): unknown;
}>();

useGalleryFilterUrl();
useGalleryOrderUrl();
useGalleryViewModeUrl();

const { t } = useI18n();
const route = useRoute();
const galleryRoms = storeGalleryRoms();
const galleryFilterStore = storeGalleryFilter();
const gallerySelection = storeGallerySelection();
const selectionInput = useGallerySelectionInput();
const scrollRestoration = storeScrollRestoration();
const {
  searchTerm,
  filterMatched,
  filterFavorites,
  filterDuplicates,
  filterPlayables,
  filterMissing,
  filterPhysical,
  filterVerified,
  filterRA,
  filterSaves,
  filterStates,
  filterSoundtrack,
  selectedPlatforms,
  selectedGenres,
  selectedFranchises,
  selectedCollections,
  selectedCompanies,
  selectedPublishers,
  selectedDevelopers,
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
  publishersLogic,
  developersLogic,
  ageRatingsLogic,
  regionsLogic,
  languagesLogic,
  playerCountsLogic,
  metadataProvidersLogic,
  tagsLogic,
  statusesLogic,
  selectedLengthMinHours,
  selectedLengthMaxHours,
} = storeToRefs(galleryFilterStore);

// Drawer open state — bound to FilterDrawer via v-model.
const filterDrawerOpen = ref(false);

// Active filter count — drives the toolbar badge. Counts each
// boolean/tri-state filter that's set, plus each multi-select group
// with at least one selection. Mirrors `FilterDrawer`'s own count so
// the badge agrees with the drawer header.
const filterActiveCount = computed(() => {
  let n = 0;
  if (filterMatched.value !== null) n += 1;
  if (filterFavorites.value !== null) n += 1;
  if (filterDuplicates.value !== null) n += 1;
  if (filterPlayables.value !== null) n += 1;
  if (filterMissing.value !== null) n += 1;
  if (filterPhysical.value !== null) n += 1;
  if (filterVerified.value !== null) n += 1;
  if (filterRA.value !== null) n += 1;
  if (filterSaves.value !== null) n += 1;
  if (filterStates.value !== null) n += 1;
  if (filterSoundtrack.value !== null) n += 1;
  if (selectedPlatforms.value.length > 0) n += 1;
  for (const arr of [
    selectedGenres,
    selectedFranchises,
    selectedCollections,
    selectedCompanies,
    selectedPublishers,
    selectedDevelopers,
    selectedAgeRatings,
    selectedRegions,
    selectedLanguages,
    selectedPlayerCounts,
    selectedMetadataProviders,
    selectedTags,
    selectedStatuses,
  ]) {
    if (arr.value.length > 0) n += 1;
  }
  if (
    selectedLengthMinHours.value !== null ||
    selectedLengthMaxHours.value !== null
  ) {
    n += 1;
  }
  return n;
});

// Filter changes → refetch the gallery. Mirrors the search debounced
// path (invalidate windows + bootstrap initial metadata). The watch
// fires only on subsequent changes; the initial hydration done by
// `useGalleryFilterUrl` happens before this watch is set up and so
// does not echo here.
watch(
  [
    filterMatched,
    filterFavorites,
    filterDuplicates,
    filterPlayables,
    filterMissing,
    filterPhysical,
    filterVerified,
    filterRA,
    filterSaves,
    filterStates,
    filterSoundtrack,
    selectedPlatforms,
    selectedGenres,
    selectedFranchises,
    selectedCollections,
    selectedCompanies,
    selectedPublishers,
    selectedDevelopers,
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
    publishersLogic,
    developersLogic,
    ageRatingsLogic,
    regionsLogic,
    languagesLogic,
    playerCountsLogic,
    metadataProvidersLogic,
    tagsLogic,
    statusesLogic,
    selectedLengthMinHours,
    selectedLengthMaxHours,
  ],
  () => {
    galleryRoms.invalidateWindows();
    void galleryRoms.fetchInitialMetadata();
  },
  { deep: true },
);

const { supportsWebp } = useWebpSupport();

const { total, charIndex, initialFetching, orderBy, orderDir } =
  storeToRefs(galleryRoms);

const { groupBy, layout, toolbarPosition } = useGalleryMode();

// Responsive columns — measure the section to chunk roms into rows.
// Card width and inset track the breakpoint so phones pack more, smaller
// cards instead of one stretched card per row:
//   inset  = scroller padding (--r-row-pad × 2), plus the AlphaStrip column
//            (`--r-alpha-strip-w` + its gap) wherever the strip renders
//   card   = matches the `--r-card-art-w` the shell sets per breakpoint
//            (108 on xs, 158 otherwise) so the JS row-chunking and the
//            CSS grid `minmax(--r-card-art-w, 1fr)` stay in lock-step.
const { xs, smAndDown } = useBreakpoint();
const sectionEl = ref<HTMLElement | null>(null);
// A jump to "M" means nothing when the gallery is sorted by size or date, so
// the letter affordances go away with the letters themselves.
const lettersSupported = computed(() => orderSupportsLetters(orderBy.value));
const stripVisible = computed(() => !smAndDown.value && lettersSupported.value);
const jumpMenuVisible = computed(
  () => smAndDown.value && lettersSupported.value,
);
// The strip's footprint: its letter column plus `--r-alpha-strip-gap`.
const STRIP_INSET_PX =
  parseInt(layoutTokens.alphaStripWidth, 10) + parseInt(space[3], 10);
// Card-art width reference (matches GameCard's `--r-card-art-w`); sets the
// fixed card HEIGHT (a 2/3 cover at this width). Real width follows the ratio.
const CARD_GAP_PX = 12;
const cardWidth = () => (xs.value ? 130 : 158);
const cardHeight = () => Math.round(cardWidth() / (2 / 3));
const { columns, usableWidth } = useResponsiveColumns(sectionEl, {
  cardWidth,
  gap: CARD_GAP_PX,
  inset: () =>
    (xs.value ? 28 : smAndDown.value ? 40 : 72) +
    (stripVisible.value ? STRIP_INSET_PX : 0),
});

// Fallback cover ratio (boxart style) — the per-card `--r-cover-ratio` seed
// before GameCover measures the real image, plus the bootstrap skeletons.
// The flow-packer takes it too (`fallbackRatio`): a card with no artwork
// paints its placeholder at this ratio and never reports a measured one, so
// packing it as box art would under-reserve its width and overflow the row.
const { boxartStyle } = useUISettings();
const coverAspectRatio = computed(() =>
  coverRatio(
    isBoxartStyle(boxartStyle.value) ? boxartStyle.value : "cover_path",
  ),
);

// Measured natural cover ratios feeding the flow-packer — GameCard reports
// each cover's ratio on load (`onCardRatio`), the packer reads `ratioAt`,
// and `ratioVersion` bumps (debounced) to trigger a single re-pack.
const { ratioVersion, ratioAt, onCardRatio } = useGalleryCoverRatios();

// The list row's natural min-width (all fixed tracks + the title floor). Fed
// to the virtual scroller as `minContentWidth` in list mode so a viewport
// narrower than the columns scrolls the list HORIZONTALLY instead of clipping
// them. Also drives the sticky column header's width so it scrolls in step.
// Less the rows' leading padding, which sits in the gutter they bleed into.
const listMinWidth = computed(
  () => getListMinWidth(props.showPlatformColumn) - LIST_ROW_PAD_X_PX,
);

// Compact list rows (phones / tablets) open one detail panel at a time; the
// virtualiser reads the same position to give that row its taller slot.
const listExpansion = useListExpansion();
watch(
  [
    layout,
    smAndDown,
    () => galleryRoms.total,
    () => galleryRoms.orderBy,
    () => galleryRoms.orderDir,
  ],
  listExpansion.collapse,
);

// 2D arrow / gamepad nav for both layouts of the gallery. Two passes:
//   * Grid mode — rows are `.r-v2-shell__row` (the per-virtualizer-item
//     wrapper around the row's GameCards). ArrowLeft/Right within a row,
//     ArrowUp/Down jumps to the same column in the next row.
//   * List mode — each `.game-list-row` is both row and cell. ArrowLeft/
//     Right is no-op (single cell per row); ArrowUp/Down moves between
//     rows.
// Both call sites resolve `current()` against the same focused element
// and only the matching one actually moves focus, so they don't fight.
// Virtualised rows past the overscan window simply aren't in the DOM —
// nav clamps at the boundary; scrolling past mounts more rows.
useGridNav(sectionEl, { rowSelector: ".r-v2-shell__row" });
useGridNav(sectionEl, {
  rowSelector: ".game-list-row",
  getCells: (row) => [row],
});

const loadingInitial = computed(
  () => initialFetching.value && total.value === 0,
);

const notFoundRef = computed(() => props.notFound);
// An empty result under a search or filters says why, not that the view is empty.
const emptyMessageRef = computed(() => {
  if (searchTerm.value) {
    return t("rom.no-games-match-query", { query: searchTerm.value });
  }
  if (filterActiveCount.value > 0) return t("rom.no-games-match-filters");
  return props.emptyMessage;
});
const notFoundMessageRef = computed(
  () => props.notFoundMessage ?? props.emptyMessage,
);

const { virtualItems, letterToIndex, availableLetters, getItemHeight } =
  useGalleryVirtualItems({
    layout,
    groupBy,
    total,
    charIndex,
    columns,
    loadingInitial,
    emptyMessage: emptyMessageRef,
    notFound: notFoundRef,
    notFoundMessage: notFoundMessageRef,
    skeletonRowCount: props.skeletonRowCount,
    cardHeight,
    rowWidth: usableWidth,
    gap: CARD_GAP_PX,
    ratioAt,
    ratioVersion,
    listSettledDetail: listExpansion.settledPanelHeight,
    fallbackRatio: coverAspectRatio,
  });

const scrollerRef = ref<InstanceType<typeof RVirtualScroller> | null>(null);

// Where the open row sits in the packed list. Recomputed when a row opens or
// the list re-packs, never on the animation's frames.
const expandedIndex = computed(() => {
  const position = listExpansion.expandedPosition.value;
  if (position == null) return -1;
  return virtualItems.value.findIndex(
    (item) => item.kind === "list-row" && item.position === position,
  );
});
const listOffsetShift = computed(() =>
  expandedIndex.value < 0
    ? undefined
    : { fromIndex: expandedIndex.value, px: listExpansion.shiftPx.value },
);

// ── Toolbar ─────────────────────────────────────────────────────────
const scrollTopNow = computed(() => scrollerRef.value?.scrollTop ?? 0);
const { toolbarHeight, pinDistance, pinned, bindToolbar, bindSentinel } =
  usePinnedToolbar(scrollTopNow);
// The floating dock leaves no toolbar to pin, so a sentinel above the column
// header marks when that header reaches the top bar.
const listHeaderSentinel = ref<HTMLElement | null>(null);
const listHeaderAtTop = ref(false);
useIntersectionObserver(
  listHeaderSentinel,
  ([entry]) => {
    listHeaderAtTop.value =
      !!entry?.rootBounds &&
      !entry.isIntersecting &&
      entry.boundingClientRect.top < entry.rootBounds.top;
  },
  {
    root: computed(() => scrollerRef.value?.containerEl ?? null),
    rootMargin: `-${layoutTokens.navHeight} 0px 0px 0px`,
  },
);
const listHeaderPinned = computed(() =>
  toolbarPosition.value === "floating" ? listHeaderAtTop.value : pinned.value,
);
// The AlphaStrip follows the toolbar down until it pins: a scroll-driven
// animation (hence `timeline-scope`), else a style write on the strip alone.
const supportsScrollTimeline =
  typeof CSS !== "undefined" &&
  CSS.supports("animation-timeline: scroll()") &&
  CSS.supports("timeline-scope: --a");
const stripRef = ref<InstanceType<typeof AlphaStrip> | null>(null);
if (!supportsScrollTimeline) {
  const stripShift = computed(() =>
    Math.max(0, pinDistance.value - scrollTopNow.value),
  );
  watchEffect(() => {
    (stripRef.value?.$el as HTMLElement | undefined)?.style.setProperty(
      "--r-v2-shell-strip-shift",
      `${stripShift.value}px`,
    );
  });
}

// ── Viewport range / AlphaStrip / dwell prefetch ────────────────────
const viewportRange = ref<{ first: number; last: number }>({
  first: 0,
  last: -1,
});
function onViewportRangeChange(range: { first: number; last: number }) {
  viewportRange.value = range;
  scheduleFetchSync(range);
}

// Rows kept rendered beyond the viewport. Adaptive so the rendered CARD count
// stays bounded regardless of how many columns fit: a fixed row overscan on a
// wide screen (~9 cards/row) mounts hundreds of off-screen cards, and each
// card is an expensive subtree (cover + hover overlay + shared game actions).
// We target a roughly constant overscan-card budget per side, clamped so a
// single-column phone keeps enough rows for smooth scrolling without
// overshooting. List rows are one item each → a flat row count is fine.
const GRID_OVERSCAN_CARDS = 60;
const virtualOverscan = computed(() =>
  layout.value === "list"
    ? 12
    : Math.min(
        20,
        Math.max(
          4,
          Math.round(GRID_OVERSCAN_CARDS / Math.max(1, columns.value)),
        ),
      ),
);

// ── Debug overlay bridge ────────────────────────────────────────────
// Publish the virtual scroller's window stats so the global DebugOverlay
// can show whether windowing is actually trimming the DOM as you scroll.
// Gated on `debugMode`: when off the effect early-returns before reading
// any scroll state, so it never re-runs on scroll (zero runtime cost).
const { enabled: debugMode } = useDebugMode();
const virtualDebug = useVirtualScrollDebug();

watchEffect(() => {
  if (!debugMode.value) {
    virtualDebug.clear();
    return;
  }
  const items = virtualItems.value;
  const total = items.length;
  const vr = viewportRange.value;
  const empty = total === 0 || vr.last < vr.first;
  const overscan = virtualOverscan.value;
  const first = empty ? 0 : Math.max(0, vr.first - overscan);
  const last = empty ? -1 : Math.min(total - 1, vr.last + overscan);
  // Count the cards actually mounted in the rendered window — grid rows fan
  // out into many cards, so this is the real DOM weight (not just row count).
  let renderedCards = 0;
  for (let i = first; i <= last; i++) {
    const it = items[i];
    if (!it) continue;
    if (it.kind === "row") renderedCards += it.endPosition - it.startPosition;
    else if (it.kind === "skeleton-row")
      renderedCards += Math.max(1, columns.value);
    else renderedCards += 1;
  }
  virtualDebug.publish({
    label: layout.value === "list" ? "gallery·list" : "gallery·grid",
    total,
    renderedRows: empty ? 0 : last - first + 1,
    renderedCards,
    viewportFirst: vr.first,
    viewportLast: vr.last,
    overscan,
    scrollTop: scrollerRef.value?.scrollTop ?? 0,
  });
});

const visibleLettersSet = computed<Set<string>>(() => {
  const set = new Set<string>();
  const r = viewportRange.value;
  if (r.last < r.first) return set;
  const items = virtualItems.value;
  for (let i = r.first; i <= r.last; i++) {
    const it = items[i];
    if (!it) continue;
    if (it.kind === "letter-header") set.add(it.letter);
    else if (it.kind === "row") for (const l of it.letters) set.add(l);
    else if (it.kind === "list-row") set.add(it.letter);
  }
  return set;
});

const currentLetter = computed<string>(() => {
  const r = viewportRange.value;
  if (r.last < r.first) return "";
  const items = virtualItems.value;
  for (let i = r.first; i <= r.last; i++) {
    const it = items[i];
    if (!it) continue;
    if (it.kind === "letter-header") return it.letter;
    if (it.kind === "row" && it.letters.length > 0) return it.letters[0];
    if (it.kind === "list-row") return it.letter;
  }
  return "";
});

// Viewport-driven windowed fetch. The shell collects which positions are
// currently visible (from the rows in `viewportRange`, for both grid and
// list layouts) and hands them to the store's `syncVisibleWindows`, which
// aligns each to its shared 72-item window, dedupes, starts the windows
// covering the viewport, and cancels any that scrolled out of view.
// Batching visible cards into a handful of paginated `getRoms` requests
// (instead of one request per card) is what keeps a fast scroll — or two
// users scrolling at once — from flooding the single-worker backend.
//
// A small debounce on viewport changes prevents fire-and-cancel storms
// during smooth scrolling — only when the viewport settles for
// `FETCH_DEBOUNCE_MS` do we sync. Both layouts share this one path, so the
// list is debounced too (list rows no longer self-fetch on mount).
const FETCH_DEBOUNCE_MS = 80;
let fetchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let pendingRange: { first: number; last: number } | null = null;

function collectVisiblePositions(range: {
  first: number;
  last: number;
}): Set<number> {
  const out = new Set<number>();
  if (range.last < range.first) return out;
  const items = virtualItems.value;
  for (let i = range.first; i <= range.last; i++) {
    const it = items[i];
    if (!it) continue;
    // Grid rows fan out into a contiguous run of card positions; list rows
    // carry a single position each.
    if (it.kind === "row") {
      for (let p = it.startPosition; p < it.endPosition; p++) out.add(p);
    } else if (it.kind === "list-row") {
      out.add(it.position);
    }
  }
  return out;
}

function syncFetches(range: { first: number; last: number }) {
  galleryRoms.syncVisibleWindows(collectVisiblePositions(range));
}

function scheduleFetchSync(range: { first: number; last: number }) {
  pendingRange = range;
  if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
  fetchDebounceTimer = setTimeout(() => {
    fetchDebounceTimer = null;
    if (pendingRange) {
      syncFetches(pendingRange);
      pendingRange = null;
    }
  }, FETCH_DEBOUNCE_MS);
}

// When the virtualItems list itself changes (gallery context switch,
// search invalidate), drop the pending debounced sync. The store's
// `invalidateWindows` / `resetGallery` already aborts every in-flight
// request, so we just clear local state.
watch(virtualItems, () => {
  if (fetchDebounceTimer) {
    clearTimeout(fetchDebounceTimer);
    fetchDebounceTimer = null;
  }
  pendingRange = null;
  // Re-sync against the current viewport so visible rows in the new
  // context start fetching immediately (no debounce — items just
  // changed, the user is staring at skeletons).
  syncFetches(viewportRange.value);
});

// A jump holds its letter under the toolbar until the user scrolls again, so
// a slow landing window still ends up anchored. The cap covers the viewer who
// walks away mid-jump.
const LETTER_JUMP_MAX_MS = 15000;
const jumpLetter = ref<string | null>(null);
let jumpDeadline = 0;

function anchorLetter(letter: string, smooth: boolean) {
  const idx = letterToIndex.value.get(letter);
  if (idx == null) return;
  // The section runs under the top bar, so rows land below it in either dock.
  const section = sectionEl.value;
  const navHeight = section
    ? parseFloat(getComputedStyle(section).getPropertyValue("--r-nav-h")) || 0
    : 0;
  const stickyOffset =
    navHeight +
    toolbarHeight.value +
    (layout.value === "list" ? LIST_HEADER_HEIGHT_PX : 0);
  scrollerRef.value?.scrollToIndex(idx, { smooth, stickyOffset });
}

function scrollToLetter(letter: string) {
  jumpLetter.value = letter;
  jumpDeadline = Date.now() + LETTER_JUMP_MAX_MS;
  anchorLetter(letter, true);
  // The viewport-driven fetch sync handles the destination — once the
  // smooth scroll settles, `update:viewportRange` fires and the windows at
  // the landing zone start loading via `syncFetches` (both layouts). No
  // manual prefetch needed.
}

/** Gives the scroll back to the user, whatever a jump was still correcting. */
function endLetterJump() {
  jumpLetter.value = null;
}

/** The letter still worth correcting towards, or null once the cap is up. */
function pendingJumpLetter(): string | null {
  const letter = jumpLetter.value;
  if (!letter) return null;
  if (Date.now() > jumpDeadline) {
    endLetterJump();
    return null;
  }
  return letter;
}

// The smooth scroll animates towards the target the jump computed; anything
// that moved meanwhile (a re-pack, the header rendering) leaves it short, so
// settle onto the letter once the animation stops.
function reanchorToJump() {
  const letter = pendingJumpLetter();
  if (letter) anchorLetter(letter, false);
}

// Three things move a letter out from under the toolbar after a jump: the
// landing window arriving, the covers re-packing the rows, and the view header
// rendering late. Re-anchor on each. Watching the packed items rather than
// `letterToIndex` keeps that map lazy, built only when a jump needs it.
watch(
  [
    virtualItems,
    () => scrollerRef.value?.innerOffsetTop ?? 0,
    () => galleryRoms.loadedWindows.size,
  ],
  reanchorToJump,
);

// ── Search filter (debounced) ───────────────────────────────────────
const searchInput = ref(searchTerm.value ?? "");
let searchDebounce: ReturnType<typeof setTimeout> | null = null;
function setSearch(value: string) {
  searchInput.value = value;
  if (searchDebounce) clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => {
    const normalized = value.trim();
    if (normalized === (searchTerm.value ?? "")) return;
    searchTerm.value = normalized || null;
    // Both layouts share the same loading model: invalidate and
    // bootstrap metadata only; rows hydrate per-position via the row
    // component's mount lifecycle (grid: GameCard via shell-level
    // viewport-sync; list: GameListRow via its own onMounted).
    galleryRoms.invalidateWindows();
    void galleryRoms.fetchInitialMetadata();
  }, 300);
}

// ── Sort ──────────────────────────────────────────────────────────
// Both affordances (list column headers, grid direction toggle) only
// write the store; `useGalleryOrderUrl` mirrors it to the URL and the
// watch below owns the refetch.
const listSortKey = computed<ListSortKey | null>(() => {
  const key = orderBy.value;
  return isListSortKey(key) ? key : null;
});

function onListSort(payload: { key: ListSortKey; dir: "asc" | "desc" }) {
  galleryRoms.setOrderBy(payload.key);
  galleryRoms.setOrderDir(payload.dir);
}

// The toolbar's sort axes, matching the list column headers.
const sortOptions = computed(() => getSortOptions(props.showPlatformColumn));

// Watching the store rather than refetching inside the handlers also
// covers the URL-driven writes (back/forward, a pasted link). The
// initial URL hydration runs before this watch is set up, so it does
// not echo here.
watch([orderBy, orderDir], () => {
  galleryRoms.invalidateWindows();
  void galleryRoms.fetchInitialMetadata();
});

// ── Scroll restoration ─────────────────────────────────────────────
async function applyRestoredScroll() {
  const saved = scrollRestoration.restore(route.fullPath);
  if (saved == null) return;
  const root = scrollerRef.value?.containerEl;
  if (!root) return;
  await nextTick();
  root.scrollTop = saved;
}

function saveCurrentScroll(routeFullPath: string) {
  const root = scrollerRef.value?.containerEl;
  if (root) scrollRestoration.save(routeFullPath, root.scrollTop);
}

onBeforeRouteUpdate((to, from) => {
  saveCurrentScroll(from.fullPath);
  // Search, filters, sort and view mode live in the query, so they
  // navigate without leaving the gallery and keep the selection. Only a
  // path change is a real context switch, where it would read as stale.
  if (to.path === from.path) return;
  gallerySelection.clear();
});
onBeforeRouteLeave((_to, from) => {
  saveCurrentScroll(from.fullPath);
  gallerySelection.clear();
});

// Whole-result select-all, shared with the SelectionBar button and
// the list header checkbox.
const { selectAll, selectingAll } = useGallerySelectAll();

// Esc clears the selection, Ctrl/Cmd+A selects the whole result; both
// skip editable elements so the search field's native Cmd+A survives.
function onShellKey(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null;
  if (
    target &&
    (target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable)
  ) {
    return;
  }
  // `selectingAll` keeps Esc working while a whole-result fetch is
  // still in flight with nothing selected yet (clear() abandons it).
  if (e.key === "Escape" && (gallerySelection.enabled || selectingAll.value)) {
    e.preventDefault();
    gallerySelection.clear();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A")) {
    e.preventDefault();
    // A held chord repeats keydown at the OS rate; one trigger is enough.
    if (!e.repeat) void selectAll();
  }
}

// Gallery owns its own internal scroll (the RVirtualScroller). The
// section is sized to one viewport exactly, but pixel-rounding
// or transient layout shifts can still produce a stray 1-2px document
// overflow → a phantom doc scrollbar competing with the virtualizer.
// Locking the body's overflow while the shell is mounted guarantees
// the only scrollbar visible on gallery routes is the virtualizer's.
let prevBodyOverflow: string | null = null;

onMounted(() => {
  prevBodyOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  window.addEventListener("keydown", onShellKey);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onShellKey);
  // A press still in flight would otherwise fire its timer into whatever
  // replaces this gallery.
  selectionInput.cancel();
  // Selection is gallery-scoped: leaving the shell drops it so a
  // navigation back to a non-gallery view (Home, Settings) doesn't
  // keep stale picks alive.
  gallerySelection.clear();
  if (searchDebounce) clearTimeout(searchDebounce);
  if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
  // When leaving the gallery entirely, stop any in-flight window fetches so
  // navigating away mid-scroll doesn't keep the network / backend busy.
  // Keeps the hydrated cache so returning to the same gallery is instant.
  galleryRoms.abortInFlight();
  // Drop the debug stats so the overlay doesn't show stale gallery numbers
  // on the next (non-gallery) route.
  virtualDebug.clear();
  // Restore body overflow so non-gallery routes scroll normally.
  document.body.style.overflow = prevBodyOverflow ?? "";
  prevBodyOverflow = null;
});

// ── Slot helpers ────────────────────────────────────────────────────
function getRomAt(p: number) {
  return galleryRoms.getRomAt(p);
}

function rowPositions(row: {
  startPosition: number;
  endPosition: number;
}): number[] {
  const out: number[] = [];
  for (let p = row.startPosition; p < row.endPosition; p++) out.push(p);
  return out;
}

type RowItem = Extract<GalleryItem, { kind: "row" }>;
type LetterHeaderItem = Extract<GalleryItem, { kind: "letter-header" }>;
type EmptyItem = Extract<GalleryItem, { kind: "empty" }>;
type ListRowItem = Extract<GalleryItem, { kind: "list-row" }>;
const asRow = (i: GalleryItem) => i as RowItem;
const asLetterHeader = (i: GalleryItem) => i as LetterHeaderItem;
const asEmpty = (i: GalleryItem) => i as EmptyItem;
const asListRow = (i: GalleryItem) => i as ListRowItem;
const itemKind = (i: GalleryItem) => i.kind;

// Stable identity for the virtualiser. Each GalleryItem carries a content-
// derived `key` (`row-${start}`, `lh-${letter}`, `lr-${p}`, …); feeding it to
// RVirtualScroller as `get-item-key` lets Vue MATCH rows across a re-pack and
// MOVE the unchanged ones instead of patching by array index. Index-keying
// (the default) reassigns every slot's content when a re-pack inserts/removes
// a row above the viewport, remounting every visible card (image re-decode +
// reveal). With identity keys, a moved row keeps its DOM and its inner cards
// (keyed by `:key="p"`) patch in place. `unknown` matches the prop signature.
const galleryItemKey = (item: unknown): string => (item as GalleryItem).key;

// View-facing surface. Methods only — internal state stays internal.
defineExpose({
  /** Re-apply the previously-saved scroll position for the current route
   * (typically called by the view at the end of its load flow). */
  applyRestoredScroll,
  /** Force-save the current scrollTop to a specific routeFullPath.
   * The shell already saves on `onBeforeRouteUpdate` / `onBeforeRouteLeave`
   * automatically; this is for one-off checkpoints. */
  saveCurrentScroll,
});
</script>

<template>
  <section
    ref="sectionEl"
    class="r-v2-shell"
    :class="{
      'r-v2-shell--list': layout === 'list',
      'r-v2-shell--floating': toolbarPosition === 'floating',
      'r-v2-shell--no-strip': !stripVisible,
    }"
    :style="{
      '--r-v2-shell-toolbar-h': `${toolbarHeight}px`,
      '--r-v2-shell-pin-distance': `${pinDistance}px`,
      '--r-cover-ratio': coverAspectRatio,
      '--r-list-min-w': `${listMinWidth}px`,
    }"
  >
    <RVirtualScroller
      ref="scrollerRef"
      :items="virtualItems"
      :get-item-height="getItemHeight"
      :get-item-key="galleryItemKey"
      :offset-shift="listOffsetShift"
      :overscan="virtualOverscan"
      :min-content-width="
        layout === 'list' && !smAndDown ? listMinWidth : undefined
      "
      class="r-v2-shell__scroller r-v2-scroll-hidden"
      :tabindex="-1"
      @wheel.passive="endLetterJump"
      @pointerdown.passive="endLetterJump"
      @keydown="endLetterJump"
      @scrollend="reanchorToJump"
      @update:viewport-range="onViewportRangeChange"
    >
      <!-- HEADER (Section 1) + TOOLBAR (Section 2). Both live in the
           scroller's flow: the header scrolls away under the top bar, and
           the toolbar pins right below the top bar as a glass strip. -->
      <template #prepend>
        <template v-if="hasHeader">
          <div class="r-v2-shell__header">
            <slot name="header" />
          </div>
          <RDivider class="r-v2-shell__header-divider" />
        </template>
        <div v-else class="r-v2-shell__nav-spacer" />

        <template v-if="toolbarPosition === 'header'">
          <div :ref="bindSentinel" aria-hidden="true" />
          <div
            :ref="bindToolbar"
            class="r-v2-shell__toolbar r-pinned-toolbar"
            :class="{ 'r-pinned-toolbar--pinned': pinned }"
          >
            <GalleryToolbar
              :group-by="groupBy"
              :layout="layout"
              :position="toolbarPosition"
              :sort-dir="orderDir"
              :sort-key="listSortKey"
              :sort-key-items="sortOptions"
              show-search
              :search="searchInput"
              :search-placeholder="searchPlaceholder"
              :autofocus-search="autofocusSearch"
              show-filter
              :filter-active-count="filterActiveCount"
              @update:group-by="groupBy = $event"
              @update:layout="layout = $event"
              @update:sort-dir="galleryRoms.setOrderDir"
              @update:sort-key="galleryRoms.setOrderBy"
              @update:search="setSearch"
              @click:filter="filterDrawerOpen = true"
            >
              <template #actions>
                <AlphaJumpMenu
                  v-if="jumpMenuVisible"
                  :available="availableLetters"
                  :current="currentLetter"
                  :direction="orderDir"
                  @pick="scrollToLetter"
                />
              </template>
            </GalleryToolbar>
          </div>
        </template>

        <!-- LIST COLUMN HEADER — sticky below the toolbar in list mode.
             Shares `LIST_GRID_TEMPLATE` with every GameListRow underneath
             so columns align. Header click cycles asc/desc into the
             store's orderBy/orderDir. -->
        <template v-if="layout === 'list'">
          <div
            v-if="toolbarPosition === 'floating'"
            ref="listHeaderSentinel"
            aria-hidden="true"
          />
          <GameListHeader
            class="r-v2-shell__list-header"
            :class="{ 'r-pinned-list-header': listHeaderPinned }"
            :sort-key="listSortKey"
            :sort-dir="orderDir"
            :show-platform-column="showPlatformColumn"
            @sort="onListSort"
          />
        </template>
      </template>

      <!-- GRID / TABLE (Section 3) — letter-headers + rows of cards in
           grid/grouped mode, or a single RTable in list mode. Skeleton
           rows render while the first window is in flight. The empty
           / not-found state replaces everything below the toolbar
           with a single message. -->
      <template #default="{ item }">
        <div class="r-v2-shell__item">
          <RLetterHeading
            v-if="itemKind(item as GalleryItem) === 'letter-header'"
            :label="asLetterHeader(item as GalleryItem).letter"
          />

          <div
            v-else-if="itemKind(item as GalleryItem) === 'row'"
            class="r-v2-shell__row"
          >
            <template
              v-for="(p, slotIdx) in rowPositions(asRow(item as GalleryItem))"
              :key="p"
            >
              <GameCard
                v-if="getRomAt(p)"
                class="r-v2-card-fade"
                :style="{ '--card-fade-i': slotIdx }"
                :rom="getRomAt(p)!"
                :webp="supportsWebp"
                :show-platform-badge="showPlatformBadge"
                selectable
                :position="p"
                @ratio="onCardRatio"
              />
              <GameCardSkeleton v-else />
            </template>
          </div>

          <GameListRow
            v-else-if="itemKind(item as GalleryItem) === 'list-row'"
            :position="asListRow(item as GalleryItem).position"
            :webp="supportsWebp"
            :show-platform-column="showPlatformColumn"
            expandable
            :expanded="
              listExpansion.isExpanded(asListRow(item as GalleryItem).position)
            "
            :detail-height="
              listExpansion.panelHeight(asListRow(item as GalleryItem).position)
            "
            @ratio="onCardRatio"
            @toggle-expand="
              listExpansion.toggle(asListRow(item as GalleryItem).position)
            "
          />

          <GameListSkeletonRow
            v-else-if="itemKind(item as GalleryItem) === 'skeleton-list-row'"
            :show-platform-column="showPlatformColumn"
          />

          <div
            v-else-if="itemKind(item as GalleryItem) === 'empty'"
            class="r-v2-shell__empty"
          >
            <REmptyState
              :icon="emptyIcon"
              :title="asEmpty(item as GalleryItem).message"
            />
          </div>

          <div
            v-else-if="itemKind(item as GalleryItem) === 'skeleton-row'"
            class="r-v2-shell__row"
          >
            <GameCardSkeleton
              v-for="n in Math.max(1, columns)"
              :key="`sk-${n}`"
            />
          </div>
        </div>
      </template>
    </RVirtualScroller>

    <!-- ALPHASTRIP: A-Z jump column on the right edge of the section.
         Phones and tablets jump from the toolbar instead (AlphaJumpMenu). -->
    <AlphaStrip
      v-if="stripVisible"
      ref="stripRef"
      class="r-v2-shell__strip"
      :available="availableLetters"
      :current="currentLetter"
      :visible="visibleLettersSet"
      :direction="orderDir"
      @pick="scrollToLetter"
    />

    <!-- FLOATING-DOCK TOOLBAR — the alternative dock; sits permanently
         in the top-right and never scrolls. Mutually exclusive with
         the in-scroller header dock above. -->
    <GalleryToolbar
      v-if="toolbarPosition === 'floating'"
      class="r-v2-shell__floating"
      :group-by="groupBy"
      :layout="layout"
      :position="toolbarPosition"
      :sort-dir="orderDir"
      :sort-key="listSortKey"
      :sort-key-items="sortOptions"
      show-filter
      :filter-active-count="filterActiveCount"
      @update:group-by="groupBy = $event"
      @update:layout="layout = $event"
      @update:sort-dir="galleryRoms.setOrderDir"
      @update:sort-key="galleryRoms.setOrderBy"
      @click:filter="filterDrawerOpen = true"
    >
      <template #actions>
        <AlphaJumpMenu
          v-if="jumpMenuVisible"
          :available="availableLetters"
          :current="currentLetter"
          :direction="orderDir"
          @pick="scrollToLetter"
        />
      </template>
    </GalleryToolbar>

    <!-- FILTER DRAWER — owned by the shell so every gallery view gets
         it for free. Forwards `showPlatformsInFilter` from the view so
         single-platform pages can hide the platform multi-select. -->
    <FilterDrawer
      v-model="filterDrawerOpen"
      :show-platforms-filter="showPlatformsInFilter"
    />

    <!-- SELECTION BAR — floating bottom panel surfaced whenever the
         user has selected at least one ROM. Owns the bulk actions
         (favorite, collections, download, refresh, delete). Stays
         outside the scroller so it never scrolls away. -->
    <SelectionBar />
  </section>
</template>

<style scoped>
.r-v2-shell {
  /* AlphaStrip footprint = letter column (`--r-alpha-strip-w`, a global
     token) + gap to the viewport edge. */
  --r-alpha-strip-gap: var(--r-space-3);
  /* The strip's footprint, added to the scroller's right gutter. */
  --r-v2-shell-strip: calc(var(--r-alpha-strip-w) + var(--r-alpha-strip-gap));
  /* Lets the strip (a sibling) animate against the scroller's scroll. */
  timeline-scope: --r-v2-shell-scroll;
  flex: 1;
  display: flex;
  overflow: hidden;
  /* Explicit viewport-relative height instead of `height: 100%`.
     The parent `<main>` is a flex item, and percentage heights on
     descendants of flex-computed boxes don't always resolve in every
     browser / stacking context — when they fail to resolve the
     section becomes content-sized, the scroller inside ends up with
     `height: auto`, and overflow-y stops doing anything because
     there's nothing to overflow. A viewport height bypasses that
     fragility entirely. `dvh` (not `vh`) so the section
     matches the mobile visible viewport instead of the larger address-bar-
     hidden one, which would otherwise spill below the fold. */
  height: 100vh;
  height: 100dvh;
  /* Run up under the fixed top bar (<main> reserves its height with a top
     padding) so the header and cards scroll behind its glass, like Home. */
  margin-top: calc(-1 * var(--r-nav-h));
  position: relative;
}

/* On sm-and-down the section keeps its full-viewport height so cards
   scroll UNDER the translucent bottom tab bar (the glass effect). The layout
   <main> adds a bottom padding for the bar (natural-flow views need it);
   cancel it here with a matching negative margin so this full-height section
   doesn't push the document past one viewport — otherwise a second, global
   scroll stacks on top of the internal one. The scroller's bottom spacer
   (below) lifts the last row clear of the bar. */
html[data-bp~="sm-and-down"] .r-v2-shell {
  margin-bottom: calc(
    -1 * (var(--r-bottom-nav-h) + env(safe-area-inset-bottom))
  );
}
/* No strip to leave room for: phones and tablets jump from the toolbar, and
   a sort the letters can't address has no jump at all. */
.r-v2-shell--no-strip {
  --r-v2-shell-strip: 0px;
}

/* Compact list mode: the rows and their column header run to the screen
   edges, out of the scroller's gutter. Each keeps that gutter as its own
   padding, so only the separators and the row fill reach the edge. The shell
   publishes how far to bleed and the rows apply it themselves, so no row's
   class name is load-bearing in here. */
html[data-bp~="sm-and-down"] .r-v2-shell {
  --r-list-bleed: var(--r-row-pad);
}
html[data-bp~="sm-and-down"] .r-v2-shell__list-header {
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
}
/* Desktop list mode: the column rows and their header run out to the left
   screen edge the same way. The right gutter stays, under the AlphaStrip. */
html[data-bp~="md-and-up"] .r-v2-shell {
  --r-list-bleed-start: var(--r-row-pad);
}
html[data-bp~="md-and-up"] .r-v2-shell__list-header {
  margin-inline-start: calc(-1 * var(--r-list-bleed-start));
  padding-inline-start: max(var(--r-space-3), var(--r-list-bleed-start));
  /* Match the rows' natural width so the column header scrolls horizontally
     in step with them when the list is wider than the viewport. */
  min-width: calc(var(--r-list-min-w) + var(--r-list-bleed-start));
}

/* The horizontal pads live here so all in-flow content (header, toolbar,
   rows) shares one column. */
.r-v2-shell__scroller {
  flex: 1;
  height: 100%;
  scroll-timeline: --r-v2-shell-scroll block;
  padding: 0 calc(var(--r-row-pad) + var(--r-v2-shell-strip)) 60px
    var(--r-row-pad);
}

.r-v2-shell__item {
  width: 100%;
}

/* Header band: `display: flow-root` establishes a new block-formatting
   context so child margins don't collapse out visually. */
.r-v2-shell__header {
  display: flow-root;
  padding-top: calc(var(--r-nav-h) + 32px);
}
/* Without a header this clears the top bar instead; the scroller's padding
   can't, as it would also offset the sticky toolbar. */
.r-v2-shell__nav-spacer {
  height: var(--r-nav-h);
}

/* Divider between header and toolbar; scrolls away with the header. */
.r-v2-shell__header-divider {
  margin-bottom: 16px;
}

/* Flow-packed wrapping row: same-height, natural-width cards. The packer
   sized it to fit, so `nowrap` is safe; gaps match the packer (12) and the
   chrome math (18). `flex-start` pins every card to the same top. */
.r-v2-shell__row {
  display: flex;
  flex-wrap: nowrap;
  align-items: flex-start;
  gap: 12px;
  padding-bottom: 18px;
}
/* Never shrink: float rounding can push a "just fits" row a hair over, and
   shrinking a fixed-height card would crop its cover. Take ragged overflow
   instead (also keeps skeletons, default shrink:1, at their packed width). */
.r-v2-shell__row > * {
  flex-shrink: 0;
}

/* Card reveal animation (.r-v2-card-fade) lives in global.css — shared
   with the Home dashboard rows. */

.r-v2-shell__empty {
  padding: var(--r-space-6) 0;
}

/* Only the rows share their width with the strip column; the header, the
   divider and the toolbar run to the right edge over it. */
.r-v2-shell__header,
.r-v2-shell__header-divider,
.r-v2-shell__toolbar {
  margin-right: calc(-1 * var(--r-v2-shell-strip));
}

/* When the list scrolls horizontally (columns wider than the viewport), the
   page chrome — view header, divider and in-flow toolbar — belongs to the
   page, not the table, so pin them to the left (`left: 0`). They stay in place
   while only the column header and rows scroll sideways. `left` engages only
   while the scroller has horizontal overflow, i.e. in list mode. */
.r-v2-shell--list .r-v2-shell__header,
.r-v2-shell--list .r-v2-shell__header-divider,
.r-v2-shell--list .r-v2-shell__toolbar {
  position: sticky;
  left: 0;
}

/* List column header: sticky just below the pinned toolbar, and under it
   (z-index 3 vs 4) so it never intercepts the toolbar's pointer events. */
.r-v2-shell__list-header {
  position: sticky;
  top: calc(var(--r-nav-h) + var(--r-v2-shell-toolbar-h));
  z-index: 3;
}
/* Its pinned glass also runs under the strip column, out to the right edge. */
.r-v2-shell__list-header::before {
  right: calc(-1 * (var(--r-row-pad) + var(--r-v2-shell-strip)));
}

/* The strip overlays the scroller's right gutter from the pinned toolbar's
   bottom edge, shifted down with the toolbar until it pins. */
.r-v2-shell .r-v2-shell__strip {
  position: absolute;
  top: calc(var(--r-nav-h) + var(--r-v2-shell-toolbar-h));
  right: 0;
  bottom: 0;
  z-index: 5;
  justify-content: flex-start;
  transform: translateY(var(--r-v2-shell-strip-shift, 0px));
}
/* The column header's glass spans the strip column, so the letters start below it. */
.r-v2-shell--list .r-v2-shell__strip {
  top: calc(
    var(--r-nav-h) + var(--r-v2-shell-toolbar-h) + var(--r-list-header-h)
  );
}
/* The floating dock sits over the strip's top; centre the letters clear of it. */
.r-v2-shell--floating .r-v2-shell__strip {
  justify-content: safe center;
}
/* Shifted down, the strip's end runs below the viewport by the same amount;
   this spacer keeps its last letters scrollable into view. */
.r-v2-shell .r-v2-shell__strip::after {
  content: "";
  flex: none;
  height: var(--r-v2-shell-strip-shift, 0px);
}
@supports (animation-timeline: scroll()) and (timeline-scope: --a) {
  .r-v2-shell .r-v2-shell__strip,
  .r-v2-shell .r-v2-shell__strip::after {
    animation: r-v2-shell-strip-follow linear both;
    animation-timeline: --r-v2-shell-scroll;
    animation-range: 0px var(--r-v2-shell-pin-distance, 0px);
  }
  .r-v2-shell .r-v2-shell__strip::after {
    animation-name: r-v2-shell-strip-spacer;
  }
}
@keyframes r-v2-shell-strip-follow {
  from {
    transform: translateY(var(--r-v2-shell-pin-distance, 0px));
  }
  to {
    transform: none;
  }
}
@keyframes r-v2-shell-strip-spacer {
  from {
    height: var(--r-v2-shell-pin-distance, 0px);
  }
  to {
    height: 0;
  }
}

/* The section runs under the top bar; keep the floating dock below it. */
.r-v2-shell .r-v2-shell__floating {
  top: calc(var(--r-nav-h) + 14px);
}

/* Smaller cards on phones. Matches GameCard's own xs `--r-card-art-w` so
   skeletons and the packer's card-height reference track the real cards. */
html[data-bp~="xs"] .r-v2-shell {
  --r-card-art-w: 130px;
}

/* Last row rests clear of the bottom tab bar (the rest of the scroll passes
   under its glass). A real in-flow spacer, not `padding-bottom` — Safari /
   older Chromium drop a scroll container's bottom padding from its
   scrollable overflow, trapping the last row behind the bar. */
html[data-bp~="sm-and-down"] .r-v2-shell__scroller::after {
  content: "";
  display: block;
  height: calc(var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px);
}
html[data-bp~="xs"] .r-v2-shell__header {
  padding-top: calc(var(--r-nav-h) + 16px);
}
html[data-bp~="xs"] .r-v2-shell__row {
  gap: 12px;
}
</style>
