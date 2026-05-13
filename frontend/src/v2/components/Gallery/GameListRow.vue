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
import { RChip, RIcon, RSkeletonBlock } from "@v2/lib";
import { computed, onBeforeUnmount, onMounted } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { formatBytes, toBrowserLocale } from "@/utils";
import MoreMenu from "@/v2/components/GameActions/MoreMenu.vue";
import {
  pendingMorphName,
  useViewTransition,
} from "@/v2/composables/useViewTransition";
import storeGalleryRoms, { type SimpleRom } from "@/v2/stores/galleryRoms";
import {
  LIST_COLUMNS,
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
  LIST_GRID_TEMPLATE,
} from "./listColumns";

defineOptions({ inheritAttrs: false });

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
}

const props = withDefaults(defineProps<Props>(), {
  position: undefined,
  rom: undefined,
  webp: false,
});

const router = useRouter();
const galleryRoms = storeGalleryRoms();
const { morphTransition } = useViewTransition();
const { locale } = useI18n();

const isStatic = computed(() => props.rom !== undefined);

const rom = computed<SimpleRom | null>(() => {
  if (isStatic.value) return props.rom ?? null;
  return props.position !== undefined
    ? galleryRoms.getRomAt(props.position)
    : null;
});

const gridStyle = { gridTemplateColumns: LIST_GRID_TEMPLATE };

function coverUrl(item: SimpleRom): string | null {
  const path = item.path_cover_small ?? item.path_cover_large ?? null;
  if (!path) return item.url_cover ?? null;
  return props.webp ? path.replace(/\.(png|jpg|jpeg)$/i, ".webp") : path;
}

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

function morphStyleFor(item: SimpleRom) {
  const name = `rom-cover-${item.id}`;
  return pendingMorphName.value === name
    ? { viewTransitionName: name }
    : undefined;
}

function navigateTo(item: SimpleRom, currentTarget: HTMLElement | null) {
  const navigate = async () => {
    await router.push(`/rom/${item.id}`);
  };
  const thumb =
    currentTarget?.querySelector<HTMLElement>(".game-list-row__thumb") ?? null;
  if (!thumb) {
    void navigate();
    return;
  }
  morphTransition({ el: thumb, name: `rom-cover-${item.id}` }, navigate);
}

function onRowClick(e: MouseEvent) {
  const item = rom.value;
  if (!item) return;
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
    :class="{ 'game-list-row--clickable': !!rom }"
    :style="gridStyle"
    :href="rom ? `/rom/${rom.id}` : undefined"
    :aria-label="rom ? `Open ${rom.name ?? rom.fs_name_no_ext}` : undefined"
    :data-rom-position="position"
    :data-rom-id="rom?.id"
    @click="onRowClick"
  >
    <template v-if="rom">
      <div class="game-list-row__cell game-list-row__title">
        <div class="game-list-row__thumb" :style="morphStyleFor(rom)">
          <img
            v-if="coverUrl(rom)"
            :src="coverUrl(rom) ?? undefined"
            :alt="rom.name ?? rom.fs_name_no_ext"
            loading="lazy"
          />
          <span v-else class="game-list-row__thumb-fallback">
            {{ (rom.name ?? rom.fs_name_no_ext).slice(0, 2).toUpperCase() }}
          </span>
        </div>
        <div class="game-list-row__meta">
          <div class="game-list-row__name">
            {{ rom.name ?? rom.fs_name_no_ext }}
          </div>
          <div class="game-list-row__filename">{{ rom.fs_name }}</div>
        </div>
      </div>

      <div class="game-list-row__cell">
        {{ rom.fs_size_bytes ? formatBytes(rom.fs_size_bytes) : "—" }}
      </div>
      <div class="game-list-row__cell">{{ formatDate(rom.created_at) }}</div>
      <div class="game-list-row__cell">{{ releaseDate(rom) }}</div>
      <div class="game-list-row__cell">{{ ratingValue(rom) }}</div>

      <div class="game-list-row__cell">
        <div class="game-list-row__pills">
          <RChip
            v-for="l in rom.languages?.slice(0, 3) ?? []"
            :key="`lang-${l}`"
            size="x-small"
            variant="translucent"
          >
            {{ l }}
          </RChip>
        </div>
      </div>
      <div class="game-list-row__cell">
        <div class="game-list-row__pills">
          <RChip
            v-for="r in rom.regions?.slice(0, 3) ?? []"
            :key="`reg-${r}`"
            size="x-small"
            variant="translucent"
          >
            {{ r }}
          </RChip>
        </div>
      </div>

      <div class="game-list-row__cell game-list-row__cell--end">
        <MoreMenu :rom="rom">
          <template #activator="{ props: activatorProps }">
            <button
              v-bind="activatorProps"
              type="button"
              class="game-list-row__more"
              aria-label="More actions"
              @click.stop
            >
              <RIcon icon="mdi-dots-vertical" size="18" />
            </button>
          </template>
        </MoreMenu>
      </div>
    </template>

    <template v-else>
      <!-- Skeleton path — column-driven so widths/shape match
           `GameListSkeletonRow` without keeping a parallel set of
           magic numbers in this file. Per-cell shapes (cover, pills,
           dot) mirror the real cells underneath, so the row swap
           doesn't reflow on data arrival. -->
      <template v-for="col in LIST_COLUMNS" :key="String(col.key)">
        <div
          v-if="col.key === 'name'"
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

.game-list-row__thumb {
  width: var(--r-list-cover-w);
  height: var(--r-list-cover-h);
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
  background: var(--r-color-surface);
  display: grid;
  place-items: center;
}

.game-list-row__thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.game-list-row__thumb-fallback {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg-muted);
}

.game-list-row__meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.game-list-row__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-row__filename {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.game-list-row__pills {
  display: flex;
  flex-wrap: nowrap;
  gap: 3px;
  overflow: hidden;
}

.game-list-row__more {
  appearance: none;
  background: transparent;
  border: 0;
  padding: var(--r-space-1);
  border-radius: var(--r-radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  cursor: pointer;
  transition:
    color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.game-list-row__more:hover,
.game-list-row__more:focus-visible {
  color: var(--r-color-fg);
  background: var(--r-color-surface-hover);
}
</style>
