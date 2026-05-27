<script setup lang="ts">
// GameListRow — single row of the list-mode gallery.
//
// Owns:
//   * Per-row lazy fetch — onMount fires `fetchRomAt(position)`; the
//     store dedupes against in-flight + already-loaded. onUnmount aborts
//     the fetch via `cancelFetchAt(position)` so a fast scroll past
//     mid-flight doesn't keep server work queued for invisible rows.
//     Mirror of the per-card flow in grid mode — same "row mount =
//     entered viewport" contract via the shell's RVirtualScroller
//     overscan window.
//
//   * Skeleton ↔ real swap — when `getRomAt(position)` returns null the
//     row paints skeleton placeholders in every column; once the fetch
//     resolves it flips to the real cells. Same row height in both
//     states (no scroll reflow on hydration). Skeleton cells iterate
//     `LIST_COLUMNS` so the column widths and shape stay in sync with
//     the bootstrap-phase `GameListSkeletonRow`.
//
//   * Click → game-details navigation. Cover-thumb view transition mirrors
//     `GameCard`'s morph so navigating from list / grid into the detail
//     page lands on the same visual anchor.
import {
  RCheckbox,
  RChip,
  RPlatformIcon,
  RSkeletonBlock,
  RTooltip,
} from "@v2/lib";
import { computed, onBeforeUnmount, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import storePlatforms from "@/stores/platforms";
import { formatBytes, toBrowserLocale } from "@/utils";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import SiblingBadge from "@/v2/components/GameCard/SiblingBadge.vue";
import { useGallerySelectionInput } from "@/v2/composables/useGallerySelectionInput";
import { useViewTransition } from "@/v2/composables/useViewTransition";
import storeGalleryRoms, { type SimpleRom } from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { activeProviders } from "@/v2/utils/metadataProviders";
import {
  getListColumns,
  getListGridTemplate,
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
} from "./listColumns";

defineOptions({ inheritAttrs: false });

// Cap on how many language/region chips render before the `+N` overflow
// chip kicks in. Tuned so 4-chip lists fit on a single wrapped line
// inside the pills cell; longer lists stack to a second line with the
// `+N` chip pinned at the end. Full list lives in the RTooltip.
const PILLS_VISIBLE = 4;

interface Props {
  /** Absolute position in the active gallery (0-indexed). Drives the
   * row's per-row fetch + serves as the lookup key into the store's
   * `byPosition` map. Pass either this or `rom`, not both. */
  position?: number;
  /** Static ROM data — used by non-gallery surfaces (Settings → Missing
   * games) that already own the rom list. When provided, the row skips
   * the galleryRoms position lookup and the per-row lazy fetch. */
  rom?: SimpleRom | null;
  /** Cover variant — when the browser supports webp the thumb URL is
   * rewritten to .webp before the request. Wired from the shell so the
   * choice is decided once per gallery render, not per row. */
  webp?: boolean;
  /** Include the `platform` column. Mirrors `GameListHeader` so the row
   * stays aligned with the column header above it. */
  showPlatformColumn?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  position: undefined,
  rom: undefined,
  webp: false,
  showPlatformColumn: true,
});

const router = useRouter();
const galleryRoms = storeGalleryRoms();
const selection = storeGallerySelection();
const selectionInput = useGallerySelectionInput();
const platformsStore = storePlatforms();
const { morphTransition } = useViewTransition();
const { locale } = useI18n();

const columns = computed(() => getListColumns(props.showPlatformColumn));
const listSkeletonColumns = columns;

const isStatic = computed(() => props.rom !== undefined);

const rom = computed<SimpleRom | null>(() => {
  if (isStatic.value) return props.rom ?? null;
  return props.position !== undefined
    ? galleryRoms.getRomAt(props.position)
    : null;
});

const isSelected = computed(() =>
  !isStatic.value && rom.value ? selection.isSelected(rom.value.id) : false,
);

function onCheckboxClick(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  const item = rom.value;
  if (!item || props.position === undefined) return;
  if (e.shiftKey) {
    selectionInput.handleActivate(item, props.position, e);
    return;
  }
  selection.toggle(item, props.position);
}

const gridStyle = computed(() => ({
  gridTemplateColumns: getListGridTemplate(props.showPlatformColumn),
}));

const platformMeta = computed(() => {
  const item = rom.value;
  if (!item || item.platform_id == null) return null;
  return platformsStore.get(item.platform_id) ?? null;
});

const providers = computed(() => {
  const item = rom.value;
  return item ? activeProviders(item) : [];
});

// Status badge surfaces only when the rom actually has a play status
// set — otherwise GameActionBtn would render the dashed-circle
// "no status set" placeholder on every row, which reads as visual
// noise across a tall list. Mirrors the flags `useGameActions`
// inspects in `currentStatusKey`.
const hasStatus = computed(() => {
  const ru = rom.value?.rom_user;
  if (!ru) return false;
  return Boolean(ru.now_playing || ru.backlogged || ru.hidden || ru.status);
});

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString(toBrowserLocale(locale.value), {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function releaseDate(item: SimpleRom): string {
  const ts = item.metadatum?.first_release_date;
  if (!ts) return "—";
  return new Date(Number(ts)).toLocaleDateString(
    toBrowserLocale(locale.value),
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    },
  );
}

function ratingValue(item: SimpleRom): string {
  const r = item.metadatum?.average_rating;
  if (typeof r !== "number" || r <= 0) return "—";
  return r.toFixed(1);
}

function navigateTo(item: SimpleRom, currentTarget: HTMLElement | null) {
  const navigate = async () => {
    await router.push(`/rom/${item.id}`);
  };
  // The thumb is the `<GameCard decorative>`'s inner art element —
  // querying `.r-gc__art` reaches it through the GameCard wrapper.
  // GameCard's own `morphStyle` computed paints the reverse-paint name
  // on the same element when we come back from the detail page, so the
  // forward morph here pairs with the reverse paint automatically.
  const thumb = currentTarget?.querySelector<HTMLElement>(".r-gc__art") ?? null;
  if (!thumb) {
    void navigate();
    return;
  }
  morphTransition({ el: thumb, name: `rom-cover-${item.id}` }, navigate);
}

function onRowClick(e: MouseEvent) {
  const item = rom.value;
  if (!item) return;

  // Selection takes precedence over navigation when the gallery is in
  // selection mode or the user is using modifier-click. Same composable
  // as GameCard so grid + list behave identically.
  if (!isStatic.value && props.position !== undefined) {
    if (selectionInput.handleActivate(item, props.position, e)) return;
  }

  // Modifier keys / non-primary buttons fall through to native anchor
  // navigation so "open in new tab" still works (the `href` is wired
  // up; we just don't preventDefault here).
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
    return;
  }
  // Default click — prevent the anchor's native navigation, run the
  // morph, then push the route.
  e.preventDefault();
  navigateTo(item, e.currentTarget as HTMLElement | null);
}

function onRowPointerDown(e: PointerEvent) {
  const item = rom.value;
  if (!item || isStatic.value || props.position === undefined) return;
  selectionInput.handlePointerDown(item, props.position, e);
}
function onRowPointerMove(e: PointerEvent) {
  if (isStatic.value) return;
  selectionInput.handlePointerMove(e);
}
function onRowPointerEnd() {
  if (isStatic.value) return;
  selectionInput.handlePointerEnd();
}

onMounted(() => {
  // Static mode (rom passed as prop) skips the gallery's per-row fetch
  // entirely — the consumer already owns the rom data.
  if (isStatic.value || props.position === undefined) return;
  // Entered the overscan window — kick the per-row fetch. Store dedupes
  // against in-flight + already-loaded.
  void galleryRoms.fetchRomAt(props.position);
});

onBeforeUnmount(() => {
  if (isStatic.value || props.position === undefined) return;
  // Left the overscan window before the fetch resolved — abort so the
  // server doesn't keep building a row the user already scrolled past.
  // Idempotent if nothing was in flight.
  if (!galleryRoms.byPosition.has(props.position)) {
    galleryRoms.cancelFetchAt(props.position);
  }
});
</script>

<template>
  <a
    class="game-list-row"
    :class="{
      'game-list-row--clickable': !!rom,
      'game-list-row--selected': isSelected,
    }"
    :style="gridStyle"
    :href="rom ? `/rom/${rom.id}` : undefined"
    :aria-label="rom ? `Open ${rom.name ?? rom.fs_name_no_ext}` : undefined"
    :data-rom-position="position"
    :data-rom-id="rom?.id"
    :data-focus-key="rom ? `rom-${rom.id}` : undefined"
    @click="onRowClick"
    @pointerdown="onRowPointerDown"
    @pointermove="onRowPointerMove"
    @pointerup="onRowPointerEnd"
    @pointercancel="onRowPointerEnd"
  >
    <template v-if="rom">
      <!-- Selection cell — leftmost column. Click toggles this row;
           shift-click extends the range from the last toggled position.
           Hidden at rest; reveals on row hover / focus or whenever the
           row is selected so the user always knows which rows are
           picked. RCheckbox provides the box / fill / draw animations
           — same animation language as the GameCard checkbox in grid
           mode. -->
      <div class="game-list-row__cell game-list-row__select">
        <RCheckbox
          v-if="!isStatic"
          class="game-list-row__check"
          :model-value="isSelected"
          shape="circle"
          size="sm"
          color="primary"
          bare
          hide-details
          tabindex="-1"
          @click="onCheckboxClick"
        />
      </div>

      <div class="game-list-row__cell game-list-row__title">
        <GameCard
          :rom="rom"
          size="xs"
          :webp="webp"
          decorative
          :show-title="false"
          :show-platform-icon="false"
        />
        <div class="game-list-row__meta">
          <div class="game-list-row__name-row">
            <div class="game-list-row__name">
              {{ rom.name ?? rom.fs_name_no_ext }}
            </div>
            <div class="game-list-row__badges" @click.stop>
              <GameActionBtn
                v-if="hasStatus"
                :rom="rom"
                action="status"
                size="x-small"
                orientation="horizontal"
              />
              <SiblingBadge :rom="rom" orientation="horizontal" />
            </div>
          </div>
          <div class="game-list-row__filename">{{ rom.fs_name }}</div>
          <div
            v-if="providers.length > 0"
            class="game-list-row__providers"
            @click.stop
          >
            <span
              v-for="provider in providers"
              :key="provider.key"
              class="game-list-row__provider"
              :title="provider.title"
              :style="provider.bg ? { background: provider.bg } : undefined"
            >
              <img
                :src="`/assets/scrappers/${provider.logo}`"
                :alt="provider.title"
                width="14"
                height="14"
              />
            </span>
          </div>
        </div>
      </div>

      <div
        v-if="showPlatformColumn"
        class="game-list-row__cell game-list-row__platform"
      >
        <RPlatformIcon
          v-if="platformMeta?.slug"
          :slug="platformMeta.slug"
          :size="24"
        />
        <span class="game-list-row__platform-name">
          {{ platformMeta?.name ?? "—" }}
        </span>
      </div>

      <div class="game-list-row__cell">
        {{ rom.fs_size_bytes ? formatBytes(rom.fs_size_bytes) : "—" }}
      </div>
      <div class="game-list-row__cell">{{ formatDate(rom.created_at) }}</div>
      <div class="game-list-row__cell">{{ releaseDate(rom) }}</div>
      <div class="game-list-row__cell">{{ ratingValue(rom) }}</div>

      <div class="game-list-row__cell game-list-row__cell--pills">
        <div class="game-list-row__pills">
          <RChip
            v-for="l in (rom.languages ?? []).slice(0, PILLS_VISIBLE)"
            :key="`lang-${l}`"
            size="x-small"
            variant="translucent"
          >
            {{ l }}
          </RChip>
          <RChip
            v-if="(rom.languages?.length ?? 0) > PILLS_VISIBLE"
            size="x-small"
            variant="translucent"
          >
            +{{ (rom.languages?.length ?? 0) - PILLS_VISIBLE }}
          </RChip>
        </div>
        <RTooltip
          v-if="(rom.languages?.length ?? 0) > PILLS_VISIBLE"
          activator="parent"
          :text="rom.languages?.join(', ')"
          location="top"
        />
      </div>
      <div class="game-list-row__cell game-list-row__cell--pills">
        <div class="game-list-row__pills">
          <RChip
            v-for="r in (rom.regions ?? []).slice(0, PILLS_VISIBLE)"
            :key="`reg-${r}`"
            size="x-small"
            variant="translucent"
          >
            {{ r }}
          </RChip>
          <RChip
            v-if="(rom.regions?.length ?? 0) > PILLS_VISIBLE"
            size="x-small"
            variant="translucent"
          >
            +{{ (rom.regions?.length ?? 0) - PILLS_VISIBLE }}
          </RChip>
        </div>
        <RTooltip
          v-if="(rom.regions?.length ?? 0) > PILLS_VISIBLE"
          activator="parent"
          :text="rom.regions?.join(', ')"
          location="top"
        />
      </div>

      <div class="game-list-row__cell game-list-row__cell--end">
        <div class="game-list-row__actions" @click.stop>
          <GameActionBtn
            :rom="rom"
            action="favorite"
            size="small"
            variant="bare"
          />
          <GameActionBtn :rom="rom" action="more" size="small" variant="bare" />
        </div>
      </div>
    </template>

    <template v-else>
      <!-- Skeleton path — column-driven so widths/shape match
           `GameListSkeletonRow` without keeping a parallel set of
           magic numbers in this file. Per-cell shapes (cover, pills,
           dot) mirror the real cells underneath, so the row swap
           doesn't reflow on data arrival. -->
      <template v-for="col in listSkeletonColumns" :key="String(col.key)">
        <div
          v-if="col.key === 'select'"
          class="game-list-row__cell game-list-row__select"
        >
          <!-- Empty cell during skeleton phase — no placeholder so the
               selection chrome only appears once a real row exists. -->
        </div>
        <div
          v-else-if="col.key === 'name'"
          class="game-list-row__cell game-list-row__title"
        >
          <RSkeletonBlock
            :width="LIST_COVER_WIDTH_PX"
            :height="LIST_COVER_HEIGHT_PX"
          />
          <div class="game-list-row__meta">
            <RSkeletonBlock width="60%" :height="12" />
            <RSkeletonBlock width="40%" :height="10" />
          </div>
        </div>
        <div v-else-if="col.key === 'platform_id'" class="game-list-row__cell">
          <div class="game-list-row__platform">
            <RSkeletonBlock :width="24" :height="24" circle />
            <RSkeletonBlock :width="100" :height="10" />
          </div>
        </div>
        <div
          v-else-if="col.key === 'languages' || col.key === 'regions'"
          class="game-list-row__cell"
        >
          <div class="game-list-row__pills">
            <RSkeletonBlock :width="28" :height="16" rounded="pill" />
            <RSkeletonBlock :width="28" :height="16" rounded="pill" />
          </div>
        </div>
        <div
          v-else-if="col.key === 'actions'"
          class="game-list-row__cell game-list-row__cell--end"
        >
          <RSkeletonBlock :width="18" :height="18" circle />
        </div>
        <div v-else class="game-list-row__cell">
          <RSkeletonBlock :width="col.skeletonWidth ?? 60" :height="10" />
        </div>
      </template>
    </template>
  </a>
</template>

<style scoped>
.game-list-row {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-3);
  padding: 0 var(--r-space-3);
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  cursor: default;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.game-list-row--clickable {
  cursor: pointer;
}
.game-list-row--clickable:hover {
  background: var(--r-color-bg-elevated);
}

/* Selected row — brand-tinted background so the selection reads at
   a glance without competing with the per-row hover (`bg-elevated`).
   The two states can overlap (hover on a selected row); we stack the
   hover delta on top of the selected tint via `color-mix`. */
.game-list-row--selected {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
}
.game-list-row--selected.game-list-row--clickable:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
}

/* Select cell — checkbox column. Empty when the row is in skeleton
   mode so the chrome only appears once a real row is loaded. */
.game-list-row__select {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  overflow: visible;
}

/* RCheckbox carries its own visual language — we only own the row's
   reveal behaviour. Hidden at rest, visible on row hover/focus and
   whenever the row is selected. */
.game-list-row__check {
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.game-list-row:hover .game-list-row__check,
.game-list-row:focus-within .game-list-row__check,
.game-list-row--selected .game-list-row__check {
  opacity: 1;
  pointer-events: auto;
}

.game-list-row__cell {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-row__cell--end {
  display: flex;
  justify-content: flex-end;
}

.game-list-row__title {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  min-width: 0;
}

.game-list-row__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.game-list-row__name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.game-list-row__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 0 1 auto;
}

/* Inline badges next to the title — status, sibling count, etc.
   `flex-shrink: 0` keeps them visible when the name truncates. The
   SiblingBadge in GameCard absolute-positions itself over the cover;
   inline here it falls back to its natural pill layout. */
.game-list-row__badges {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.game-list-row__filename {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-row__providers {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 4px;
  overflow: hidden;
}

.game-list-row__provider {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: var(--r-color-surface);
  flex-shrink: 0;
}

.game-list-row__provider img {
  display: block;
  object-fit: contain;
}

/* Pills cell — chips wrap to multiple lines inside the cell when they
   don't fit on a single row, so short language/region lists read as a
   single horizontal strip and longer lists stack vertically. The cell
   keeps `overflow: hidden` (defense against extreme lists) and the
   row's fixed 80px height clips anything past ~3 wrapped lines; the
   full list is available via the cell's `title` tooltip. */
.game-list-row__cell--pills {
  white-space: normal;
}
.game-list-row__pills {
  display: flex;
  flex-wrap: wrap;
  align-content: center;
  gap: 3px;
  max-height: 100%;
}

.game-list-row__platform {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.game-list-row__platform-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-row__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
</style>
