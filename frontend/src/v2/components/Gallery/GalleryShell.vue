<script setup lang="ts">
// GalleryShell — shared layout for Platform / Search / Collection.
//
// Three structural sections, top to bottom, all sharing one scrollbar:
//   1. HEADER  — view-supplied via `#header` slot. Whatever the view
//                wants there: an InfoPanel with platform / collection
//                metadata, a plain PageHeader for Search, etc.
//   2. TOOLBAR — search input + group/layout/dock controls. Two-layer:
//                * `--inflow` lives in the scroller's `#prepend` slot
//                  (after the header). Visible at scrollTop=0; scrolls
//                  away with the header.
//                * `--overlay` is absolutely positioned at the top of
//                  the section, OUTSIDE the scroller. Transparent.
//                  Toggled on once the inflow toolbar has scrolled past
//                  the top — combined with `clip-path: inset(...)` on
//                  the scroller, cards are physically clipped from
//                  appearing in the toolbar's pixel band, so the
//                  overlay reveals only what's behind the section
//                  (BackgroundArt blur), never the cards.
//   3. GRID / TABLE — the row-virtualised content (cards in grid mode,
//                div-based rows in list mode — same shell scroller, same
//                AlphaStrip wiring; the list column header lives in the
//                prepend, sticky below the toolbar).
//
// Why two-layer: the user wants the toolbar to be transparent (so the
// blurred BackgroundArt shows through) AND wants cards to disappear
// when they pass behind the toolbar. With native `position: sticky`
// inside the scroller, cards passing behind a transparent element
// remain visible. Lifting the visible toolbar OUT of the scroll
// container and clipping the scroller's top band gives both: a
// see-through toolbar AND no cards leaking behind it. The inflow
// twin keeps the natural three-section flow at scrollTop=0.
//
// Cross-view behaviour owned by the shell: the virtualizer, sticky
// toolbar (two-layer) + sticky list column header, AlphaStrip,
// grid per-row dwell-debounced prefetch, scroll restoration,
// search-input debounce, URL filter sync. Each view supplies its
// header and its own resource-load flow. List rows own their per-row
// fetch lifecycle internally (mount = entered overscan window).
import { RDivider, RLetterHeading, RVirtualScroller } from "@v2/lib";
import { storeToRefs } from "pinia";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from "vue-router";
import { useUISettings } from "@/composables/useUISettings";
import storeGalleryFilter from "@/stores/galleryFilter";
import AlphaStrip from "@/v2/components/Gallery/AlphaStrip.vue";
import FilterDrawer from "@/v2/components/Gallery/FilterDrawer.vue";
import GalleryToolbar from "@/v2/components/Gallery/GalleryToolbar.vue";
import GameListHeader from "@/v2/components/Gallery/GameListHeader.vue";
import GameListRow from "@/v2/components/Gallery/GameListRow.vue";
import GameListSkeletonRow from "@/v2/components/Gallery/GameListSkeletonRow.vue";
import SelectionBar from "@/v2/components/Gallery/SelectionBar.vue";
import {
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
  type ListSortKey,
} from "@/v2/components/Gallery/listColumns";
import { GameCard, GameCardSkeleton } from "@/v2/components/GameCard";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { coverRatio, isBoxartStyle } from "@/v2/composables/useCoverArt";
import { useGalleryCoverRatios } from "@/v2/composables/useGalleryCoverRatios";
import { useGalleryFilterUrl } from "@/v2/composables/useGalleryFilterUrl";
import { useGalleryMode } from "@/v2/composables/useGalleryMode";
import { useGalleryViewModeUrl } from "@/v2/composables/useGalleryViewModeUrl";
import {
  useGalleryVirtualItems,
  type GalleryItem,
} from "@/v2/composables/useGalleryVirtualItems";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useResponsiveColumns } from "@/v2/composables/useResponsiveColumns";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import storeScrollRestoration from "@/v2/stores/scrollRestoration";

const LIST_SORT_KEYS = new Set<string>([
  "name",
  "fs_size_bytes",
  "created_at",
  "first_release_date",
  "average_rating",
]);

interface Props {
  /** Whether the header slot has content to render. False suppresses
   * the header (the prepend band collapses; toolbar pins immediately). */
  hasHeader: boolean;
  /** Toolbar's search-input placeholder. */
  searchPlaceholder: string;
  /** Empty-state message shown when the gallery resolves with zero items. */
  emptyMessage: string;
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
  /** Override the empty-state body. Receives `{ message }` (the
   * resolved empty / not-found message) so the override can decide
   * between text vs. a boxed illustration. Default: plain text. */
  empty(props: { message: string }): unknown;
}>();

useGalleryFilterUrl();
useGalleryViewModeUrl();

const route = useRoute();
const galleryRoms = storeGalleryRoms();
const galleryFilterStore = storeGalleryFilter();
const gallerySelection = storeGallerySelection();
const scrollRestoration = storeScrollRestoration();
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
  selectedStatuses,
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
  if (filterVerified.value !== null) n += 1;
  if (filterRA.value !== null) n += 1;
  if (selectedPlatforms.value.length > 0) n += 1;
  for (const arr of [
    selectedGenres,
    selectedFranchises,
    selectedCollections,
    selectedCompanies,
    selectedAgeRatings,
    selectedRegions,
    selectedLanguages,
    selectedPlayerCounts,
    selectedStatuses,
  ]) {
    if (arr.value.length > 0) n += 1;
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
    selectedStatuses,
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
//   inset  = scroller padding (--r-row-pad × 2) + AlphaStrip column (36)
//            → xs 14·2+36=64, sm 20·2+36=76, default 36·2+36=108
//   card   = matches the `--r-card-art-w` the shell sets per breakpoint
//            (108 on xs, 158 otherwise) so the JS row-chunking and the
//            CSS grid `minmax(--r-card-art-w, 1fr)` stay in lock-step.
const { xs, smAndDown } = useBreakpoint();
const sectionEl = ref<HTMLElement | null>(null);
// Card-art width reference (matches GameCard's `--r-card-art-w`); sets the
// fixed card HEIGHT (a 2/3 cover at this width). Real width follows the ratio.
const CARD_GAP_PX = 12;
const cardWidth = () => (xs.value ? 130 : 158);
const cardHeight = () => Math.round(cardWidth() / (2 / 3));
const { columns, usableWidth } = useResponsiveColumns(sectionEl, {
  cardWidth,
  gap: CARD_GAP_PX,
  inset: () => (xs.value ? 64 : smAndDown.value ? 76 : 108),
});

// Fallback cover ratio (boxart style) — the per-card `--r-cover-ratio` seed
// before GameCover measures the real image, plus the bootstrap skeletons.
const { boxartStyle } = useUISettings();
const coverAspectRatio = computed(() =>
  coverRatio(
    isBoxartStyle(boxartStyle.value) ? boxartStyle.value : "cover_path",
  ),
);

// Measured natural cover ratios feeding the flow-packer — GameCard reports
// each cover's ratio on load (`onCardRatio`), the packer reads `ratioAt`,
// and `ratioVersion` bumps (debounced) to trigger a single re-pack.
// `maxRatio` (widest cover in this gallery) drives the list view's cover
// column width.
const { ratioVersion, ratioAt, onCardRatio, maxRatio, resetMaxRatio } =
  useGalleryCoverRatios();

// List-view cover column width: the widest cover at the row's cover height,
// clamped so a portrait-only list stays tight and an outlier can't make the
// column absurd. Wide (landscape) covers then show whole instead of being
// clipped, and every row shares the width so titles stay aligned.
const listCoverWidth = computed(() => {
  const w = Math.round(LIST_COVER_HEIGHT_PX * maxRatio.value);
  return Math.min(128, Math.max(LIST_COVER_WIDTH_PX, w));
});

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
const emptyMessageRef = computed(() => props.emptyMessage);
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
  });

const scrollerRef = ref<InstanceType<typeof RVirtualScroller> | null>(null);

// ── Toolbar two-layer state ─────────────────────────────────────────
// `inflowToolbarEl` is the toolbar inside the scroller's prepend.
// `inflowToolbarTop` is its `offsetTop` within the scroller — the
// scroll threshold at which the overlay takes over. `toolbarHeight`
// drives both `scrollToIndex({ stickyOffset })` (so AlphaStrip lands
// rows below the pinned toolbar) and the scroller's clip-path inset
// (so the band the overlay covers is empty of cards).
const inflowToolbarEl = ref<HTMLElement | null>(null);
const inflowToolbarTop = ref(0);
const toolbarHeight = ref(0);
let inflowResizeObserver: ResizeObserver | null = null;

function bindInflowToolbarEl(el: HTMLElement | null) {
  inflowResizeObserver?.disconnect();
  inflowResizeObserver = null;
  inflowToolbarEl.value = el;
  if (!el) {
    inflowToolbarTop.value = 0;
    toolbarHeight.value = 0;
    return;
  }
  const measure = () => {
    inflowToolbarTop.value = el.offsetTop;
    toolbarHeight.value = el.getBoundingClientRect().height;
  };
  measure();
  // Observe the toolbar itself (height changes) and its prior siblings
  // inside the prepend (header / divider — their height shifts the
  // toolbar's `offsetTop`).
  inflowResizeObserver = new ResizeObserver(measure);
  inflowResizeObserver.observe(el);
  let prev = el.previousElementSibling;
  while (prev) {
    inflowResizeObserver.observe(prev);
    prev = prev.previousElementSibling;
  }
}

// `isStuck` flips to true the moment the inflow toolbar's top edge
// reaches the scroller's visible top. At that moment the overlay
// becomes visible and the scroller's top band is clipped, so cards
// scrolling up never reach the overlay's pixel area. Both layers
// render the toolbar UI at the same viewport y, so the swap is
// visually seamless.
const isStuck = computed(() => {
  if (toolbarPosition.value !== "header") return false;
  const scrollTop = scrollerRef.value?.scrollTop ?? 0;
  const threshold = inflowToolbarTop.value;
  if (threshold <= 0) return scrollTop > 0;
  return scrollTop >= threshold;
});

// Width / horizontal alignment of the absolute overlay needs to track
// the scroller column (which is narrowed by the AlphaStrip when it's
// rendered).
//
// The strip stays mounted in both grid and list mode regardless of how
// many letters the backend has reported — letters that aren't in
// `availableLetters` render as disabled buttons, so the layout column
// stays reserved from the very first paint (skeleton phase included).
// Without this, the scroller would shift sideways the instant the
// bootstrap response resolves and the first letter showed up.
const hasAlphaStrip = computed(
  () => layout.value === "grid" || layout.value === "list",
);

// ── Viewport range / AlphaStrip / dwell prefetch ────────────────────
const viewportRange = ref<{ first: number; last: number }>({
  first: 0,
  last: -1,
});
function onViewportRangeChange(range: { first: number; last: number }) {
  viewportRange.value = range;
  scheduleFetchSync(range);
}

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

// Per-card viewport-driven fetch. The shell tracks which positions
// are currently visible (from the rows in `viewportRange`) and keeps
// `byPosition` in sync via per-card `getRom(id)` calls — pure by-id
// DB lookups on the backend, much faster than the paginated
// `getRoms(limit/offset)` pipeline. Each fetch is independent, so
// covers stream in as their individual responses land.
//
// No idle-time prefetch: when the user stops scrolling, no new
// requests are fired. Cards already in the viewport that are still
// missing keep loading; everything off-screen waits until the user
// scrolls there.
//
// Cancellation: positions that leave the viewport while their fetch
// is in flight are aborted via `cancelFetchAt`. A small debounce on
// viewport changes prevents fire-and-cancel storms during smooth
// scrolling — only when the viewport settles for `FETCH_DEBOUNCE_MS`
// do we sync.
const FETCH_DEBOUNCE_MS = 80;
const visiblePositions = new Set<number>();
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
    if (!it || it.kind !== "row") continue;
    for (let p = it.startPosition; p < it.endPosition; p++) out.add(p);
  }
  return out;
}

function syncFetches(range: { first: number; last: number }) {
  const next = collectVisiblePositions(range);

  // Cancel positions that left the viewport before their fetch
  // resolved. The store's per-position controller handles the network
  // abort; idempotent if nothing was in flight.
  for (const p of visiblePositions) {
    if (!next.has(p) && !galleryRoms.byPosition.has(p)) {
      galleryRoms.cancelFetchAt(p);
    }
  }

  // Fire per-card fetches for positions that just entered. The store
  // dedupes against in-flight + already-loaded internally.
  for (const p of next) {
    if (!galleryRoms.byPosition.has(p)) {
      void galleryRoms.fetchRomAt(p);
    }
  }

  visiblePositions.clear();
  for (const p of next) visiblePositions.add(p);
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
// search invalidate), drop the visible-position bookkeeping. The
// store's `invalidateWindows` / `resetGallery` already aborts every
// in-flight request, so we just clear local state.
watch(virtualItems, () => {
  visiblePositions.clear();
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

// Recompute the list cover-column max when the gallery's rom set changes
// (context switch, filter, sort) so a previous platform's wide covers
// don't keep the column wide. Keyed on `romIdIndex` (not `virtualItems`)
// so grid re-packs don't trigger the O(total) rebuild.
watch(
  () => galleryRoms.romIdIndex,
  () => resetMaxRatio(),
);

// List mode pins a column header below the toolbar; AlphaStrip jumps
// must land BELOW both pinned bars or the destination row would slide
// behind the column header. Matches the height set in
// `GameListHeader.vue` — keep in sync.
const LIST_HEADER_HEIGHT = 40;

function scrollToLetter(letter: string) {
  const idx = letterToIndex.value.get(letter);
  if (idx == null) return;
  const stickyOffset =
    toolbarHeight.value + (layout.value === "list" ? LIST_HEADER_HEIGHT : 0);
  scrollerRef.value?.scrollToIndex(idx, { smooth: true, stickyOffset });
  // The viewport-driven fetch sync handles the destination — once the
  // smooth scroll settles, `update:viewportRange` fires and the cards
  // at the landing zone start loading via `syncFetches` (grid) or via
  // each `GameListRow`'s onMounted (list). No manual prefetch needed.
}

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

// ── List-mode sort ────────────────────────────────────────────────
// Header click → store order params → invalidate + bootstrap metadata.
// The grid-mode sort goes through the same path (toolbar dropdown), so
// no separate code path; list just exposes the click affordance.
const listSortKey = computed<ListSortKey | null>(() => {
  const k = orderBy.value as string;
  return LIST_SORT_KEYS.has(k) ? (k as ListSortKey) : null;
});

function onListSort(payload: { key: ListSortKey; dir: "asc" | "desc" }) {
  galleryRoms.setOrderBy(payload.key);
  galleryRoms.setOrderDir(payload.dir);
  galleryRoms.invalidateWindows();
  void galleryRoms.fetchInitialMetadata();
}

// Grid-mode direction toggle — wires the toolbar asc/desc into the
// same `orderDir` the list column-header sort writes to, then triggers
// the same invalidate+refetch path. Sort axis stays whatever the list
// last set (default "name"); grid only exposes direction.
function onGridSortDir(dir: "asc" | "desc") {
  if (galleryRoms.orderDir === dir) return;
  galleryRoms.setOrderDir(dir);
  galleryRoms.invalidateWindows();
  void galleryRoms.fetchInitialMetadata();
}

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

onBeforeRouteUpdate((_to, from) => {
  saveCurrentScroll(from.fullPath);
  // Switching to a different gallery context (Platform A → B, Search
  // query change that routes, Collection open) — the selection is
  // bound to the previous context and would read as stale items if
  // carried over. Filter / sort changes inside the same view do NOT
  // route, so they keep the selection intact (matches the rule of
  // "filter, select more, filter again").
  gallerySelection.clear();
});
onBeforeRouteLeave((_to, from) => {
  saveCurrentScroll(from.fullPath);
  gallerySelection.clear();
});

// Global hotkeys scoped to the gallery shell — Esc clears the
// selection, Ctrl/Cmd+A selects every currently-loaded rom. Both are
// guarded against editable elements so the search field's native
// Cmd+A still selects the input text.
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
  if (e.key === "Escape" && gallerySelection.enabled) {
    e.preventDefault();
    gallerySelection.clear();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "a" || e.key === "A")) {
    e.preventDefault();
    gallerySelection.selectAllLoaded(galleryRoms.byPosition.values());
  }
}

// Gallery owns its own internal scroll (the RVirtualScroller). The
// section is sized to `100vh - --r-nav-h` exactly, but pixel-rounding
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
  // Selection is gallery-scoped: leaving the shell drops it so a
  // navigation back to a non-gallery view (Home, Settings) doesn't
  // keep stale picks alive.
  gallerySelection.clear();
  if (searchDebounce) clearTimeout(searchDebounce);
  if (fetchDebounceTimer) clearTimeout(fetchDebounceTimer);
  // Cancel any per-position fetches still in flight for our last
  // visible set — `invalidateWindows` / `resetGallery` already aborts
  // window-level fetches; this covers per-card cleanup on unmount.
  for (const p of visiblePositions) {
    if (!galleryRoms.byPosition.has(p)) galleryRoms.cancelFetchAt(p);
  }
  visiblePositions.clear();
  inflowResizeObserver?.disconnect();
  inflowResizeObserver = null;
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
      'r-v2-shell--stuck': isStuck,
      'r-v2-shell--has-strip': hasAlphaStrip,
      'r-v2-shell--list': layout === 'list',
    }"
    :style="{
      '--r-v2-shell-toolbar-h': `${toolbarHeight}px`,
      '--r-cover-ratio': coverAspectRatio,
    }"
  >
    <RVirtualScroller
      ref="scrollerRef"
      :items="virtualItems"
      :get-item-height="getItemHeight"
      :overscan="25"
      class="r-v2-shell__scroller r-v2-scroll-hidden"
      @update:viewport-range="onViewportRangeChange"
    >
      <!-- HEADER (Section 1) + INFLOW TOOLBAR (Section 2 — first
           layer). Both live in the scroller's flow. The header
           scrolls away naturally; the inflow toolbar is what the user
           sees at scrollTop=0 and during the early scroll until its
           top edge reaches y=0. After that, the OVERLAY twin (below)
           takes over visually and this inflow toolbar is hidden by
           the scroller's clip-path. -->
      <template #prepend>
        <template v-if="hasHeader">
          <div class="r-v2-shell__header">
            <slot name="header" />
          </div>
          <RDivider class="r-v2-shell__header-divider" />
        </template>

        <div
          v-if="toolbarPosition === 'header'"
          :ref="(el) => bindInflowToolbarEl(el as HTMLElement | null)"
          class="r-v2-shell__toolbar r-v2-shell__toolbar--inflow"
        >
          <GalleryToolbar
            :group-by="groupBy"
            :layout="layout"
            :position="toolbarPosition"
            :sort-dir="orderDir"
            show-search
            :search="searchInput"
            :search-placeholder="searchPlaceholder"
            show-filter
            :filter-active-count="filterActiveCount"
            @update:group-by="groupBy = $event"
            @update:layout="layout = $event"
            @update:sort-dir="onGridSortDir"
            @update:search="setSearch"
            @click:filter="filterDrawerOpen = true"
          />
        </div>

        <!-- LIST COLUMN HEADER — sticky below the toolbar in list mode.
             Shares `LIST_GRID_TEMPLATE` with every GameListRow underneath
             so columns align. Header click cycles asc/desc → store
             orderBy/orderDir → invalidate + bootstrap metadata. -->
        <GameListHeader
          v-if="layout === 'list'"
          class="r-v2-shell__list-header"
          :sort-key="listSortKey"
          :sort-dir="orderDir"
          :show-platform-column="showPlatformColumn"
          :cover-width="listCoverWidth"
          @sort="onListSort"
        />
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
            :cover-width="listCoverWidth"
            @ratio="onCardRatio"
          />

          <GameListSkeletonRow
            v-else-if="itemKind(item as GalleryItem) === 'skeleton-list-row'"
            :show-platform-column="showPlatformColumn"
            :cover-width="listCoverWidth"
          />

          <div
            v-else-if="itemKind(item as GalleryItem) === 'empty'"
            class="r-v2-shell__empty"
          >
            <slot name="empty" :message="asEmpty(item as GalleryItem).message">
              {{ asEmpty(item as GalleryItem).message }}
            </slot>
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

    <!-- TOOLBAR OVERLAY (Section 2 — second layer). Absolute against
         the section, OUTSIDE the scroller. Transparent — through it,
         the BackgroundArt blur shows. Cards never appear here because
         the scroller's clip strips its top `--r-v2-shell-toolbar-h`
         band when `--stuck`.
         Mounted alongside the rest of the shell (`v-if` gates only on
         dock position) and toggled visible via `v-show` so the
         GalleryToolbar's children — RSliderBtnGroup, RTextField — run
         their initialisation animation ONCE on first render, not on
         every stuck transition. -->
    <div
      v-if="toolbarPosition === 'header'"
      v-show="isStuck"
      class="r-v2-shell__toolbar r-v2-shell__toolbar--overlay"
    >
      <GalleryToolbar
        :group-by="groupBy"
        :layout="layout"
        :position="toolbarPosition"
        :sort-dir="orderDir"
        show-search
        :search="searchInput"
        :search-placeholder="searchPlaceholder"
        show-filter
        :filter-active-count="filterActiveCount"
        @update:group-by="groupBy = $event"
        @update:layout="layout = $event"
        @update:sort-dir="onGridSortDir"
        @update:search="setSearch"
        @click:filter="filterDrawerOpen = true"
      />
    </div>

    <!-- LIST COLUMN HEADER OVERLAY — twin of the inflow list header,
         absolute against the section just below the toolbar overlay.
         The scroller's clip strips the toolbar AND list-header bands
         when `--stuck` + `--list`, so rows scrolling underneath never
         reach this pixel area — the overlay paints cleanly over the
         section's BackgroundArt blur, no see-through cards. -->
    <GameListHeader
      v-if="layout === 'list' && toolbarPosition === 'header'"
      v-show="isStuck"
      class="r-v2-shell__list-header-overlay"
      :sort-key="listSortKey"
      :sort-dir="orderDir"
      :show-platform-column="showPlatformColumn"
      :cover-width="listCoverWidth"
      @sort="onListSort"
    />

    <!-- ALPHASTRIP — A-Z jump column on the right edge of the section. -->
    <AlphaStrip
      v-if="hasAlphaStrip"
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
      :group-by="groupBy"
      :layout="layout"
      :position="toolbarPosition"
      :sort-dir="orderDir"
      show-filter
      :filter-active-count="filterActiveCount"
      @update:group-by="groupBy = $event"
      @update:layout="layout = $event"
      @update:sort-dir="onGridSortDir"
      @click:filter="filterDrawerOpen = true"
    />

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
  flex: 1;
  display: flex;
  overflow: hidden;
  /* Explicit viewport-relative height instead of `height: 100%`.
     The parent `<main>` is a flex item, and percentage heights on
     descendants of flex-computed boxes don't always resolve in every
     browser / stacking context — when they fail to resolve the
     section becomes content-sized, the scroller inside ends up with
     `height: auto`, and overflow-y stops doing anything because
     there's nothing to overflow. Subtracting the navbar from 100vh
     bypasses that fragility entirely. */
  height: calc(100vh - var(--r-nav-h));
  position: relative;
}

/* On sm-and-down the shell still fills `100vh - nav-h` so cards scroll
   UNDER the translucent bottom tab bar (the glass-blur effect). The
   scroller instead gets extra bottom padding (see below) so the last row
   comes to rest above the bar rather than trapped behind it. */

/* Scroller: padding-top moved into the prepend's first child via
   `padding-top` on the header so the inflow toolbar's `offsetTop`
   measurement isn't perturbed by the scroller's own padding. The
   horizontal pads stay here so all in-flow content (header,
   toolbar, rows) shares one column. */
.r-v2-shell__scroller {
  flex: 1;
  height: 100%;
  padding: 0 var(--r-row-pad) 60px;
}

.r-v2-shell__item {
  width: 100%;
}

/* Header band — `display: flow-root` establishes a new
   block-formatting context so child margins don't collapse out
   visually. The 32px `padding-top` provides the breathing space at
   the very top of the gallery (replacing what used to live on the
   scroller). */
.r-v2-shell__header {
  display: flow-root;
  padding-top: 32px;
}

/* Divider between header and toolbar. Lives at the bottom of the
   prepend band so it scrolls away with the header — the toolbar's
   stuck state shows no separator above it. */
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
  padding: 80px 0;
  color: var(--r-color-fg-faint);
  font-size: 13.5px;
  text-align: center;
}

/* Toolbar — both layers share the same internal styling. Transparent
   by default; the BackgroundArt behind the section shows through.
   `padding-bottom` reserves breathing space between the toolbar UI
   and the first card row in flow. */
.r-v2-shell__toolbar {
  padding-bottom: 16px;
}

/* Inflow layer — `position: sticky; top: 0` so the compositor pins
   it smoothly as the user scrolls past the header. This makes the
   inflow's pinned position match the overlay's `top: 0` exactly,
   eliminating the sub-pixel jump that an in-flow → snap-to-zero
   swap would otherwise produce. The clip-path on the scroller hides
   the inflow once `--stuck` is true, leaving only the overlay
   visible (transparent — BackgroundArt shows through, no cards). */
.r-v2-shell__toolbar--inflow {
  position: sticky;
  top: 0;
  z-index: 4;
}

/* List column header — sticky just below the toolbar. `top` matches
   the toolbar's pinned height so when both are stuck they stack
   cleanly; the toolbar's overlay layer sits at z-index 5, so we keep
   this at 3 (below the inflow toolbar's 4) to avoid intercepting
   pointer events meant for the toolbar. */
.r-v2-shell__list-header {
  position: sticky;
  top: var(--r-v2-shell-toolbar-h, 64px);
  z-index: 3;
}

/* Overlay layer — absolute against the section, mirrors the
   scroller's column (narrowed when AlphaStrip is present). z-index
   above the inflow so when both paint at y=0 (transition frame), the
   overlay stacks cleanly on top. */
.r-v2-shell__toolbar--overlay {
  position: absolute;
  top: 0;
  left: var(--r-row-pad);
  right: var(--r-row-pad);
  z-index: 5;
}
.r-v2-shell--has-strip .r-v2-shell__toolbar--overlay {
  /* AlphaStrip is a flex sibling of the scroller; the overlay must
     stop short of it so it doesn't paint over the strip. */
  right: calc(var(--r-row-pad) + 36px);
}

/* List column header overlay — twin of `.r-v2-shell__list-header`,
   positioned absolutely just below the toolbar overlay. Same column
   geometry as the toolbar overlay so columns align across both
   surfaces. z-index 4 keeps it under the toolbar overlay (5) but
   above any in-flow content peeking through. */
.r-v2-shell__list-header-overlay {
  position: absolute;
  top: var(--r-v2-shell-toolbar-h, 64px);
  left: var(--r-row-pad);
  right: var(--r-row-pad);
  z-index: 4;
}
.r-v2-shell--has-strip .r-v2-shell__list-header-overlay {
  right: calc(var(--r-row-pad) + 36px);
}

/* While stuck, clip the scroller's top toolbar-band so cards
   scrolling underneath the overlay are physically removed from
   that pixel area. The transparent overlay then reveals only the
   section's background (BackgroundArt blur) — never the cards.

   In list mode, extend the clip to also cover the list-header band
   below the toolbar so rows don't bleed through the (translucent)
   sticky column header. */
.r-v2-shell--stuck .r-v2-shell__scroller {
  clip-path: inset(var(--r-v2-shell-toolbar-h, 64px) 0 0 0);
}
.r-v2-shell--stuck.r-v2-shell--list .r-v2-shell__scroller {
  clip-path: inset(
    calc(var(--r-v2-shell-toolbar-h, 64px) + var(--r-list-header-h)) 0 0 0
  );
}

/* Smaller cards on phones. Matches GameCard's own xs `--r-card-art-w` so
   skeletons and the packer's card-height reference track the real cards. */
html[data-bp~="xs"] .r-v2-shell {
  --r-card-art-w: 130px;
}

html[data-bp~="xs"] .r-v2-shell__scroller {
  padding-left: 14px;
  padding-right: 14px;
}
/* Last row rests clear of the bottom tab bar (the rest of the scroll
   still passes under its glass). */
html[data-bp~="sm-and-down"] .r-v2-shell__scroller {
  padding-bottom: calc(
    var(--r-bottom-nav-h) + env(safe-area-inset-bottom) + 24px
  );
}
html[data-bp~="xs"] .r-v2-shell__header {
  padding-top: 16px;
}
html[data-bp~="xs"] .r-v2-shell__row {
  gap: 12px;
}
</style>
