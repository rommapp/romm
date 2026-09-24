<script setup lang="ts">
// GameListRow — single row of the list-mode gallery.
//
// Owns:
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
  RIcon,
  RMarquee,
  RPlatformIcon,
  RSkeletonBlock,
  RTooltip,
} from "@v2/lib";
import { formatPlaytime, formatReleaseDate, releaseYear } from "@v2/utils/time";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import storeCollections from "@/stores/collections";
import storePlatforms from "@/stores/platforms";
import { formatBytes, toBrowserLocale } from "@/utils";
import ProviderBadges from "@/v2/components/Gallery/ProviderBadges.vue";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import SiblingBadge from "@/v2/components/GameCard/SiblingBadge.vue";
import { useBackgroundArt } from "@/v2/composables/useBackgroundArt";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGallerySelectionInput } from "@/v2/composables/useGallerySelectionInput";
import { useStaggeredEntrance } from "@/v2/composables/useStaggeredEntrance";
import { useViewTransition } from "@/v2/composables/useViewTransition";
import { toWebpUrl } from "@/v2/composables/useWebpSupport";
import storeGalleryRoms, { type SimpleRom } from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import { activeProviders } from "@/v2/utils/metadataProviders";
import {
  getListColumns,
  getListGridTemplate,
  type ListColumn,
  LIST_COVER_HEIGHT_PX,
  LIST_COVER_WIDTH_PX,
  LIST_TITLE_SKELETON_BARS,
  LIST_TITLE_SKELETON_GAP_PX,
} from "./listColumns";

defineOptions({ inheritAttrs: false });

// Cap on how many language/region chips render before the `+N` overflow
// chip kicks in. Tuned so 4-chip lists fit on a single wrapped line
// inside the pills cell; longer lists stack to a second line with the
// `+N` chip pinned at the end. Full list lives in the RTooltip.
const PILLS_VISIBLE = 4;

interface Props {
  /** Absolute position in the active gallery (0-indexed). Serves as the
   * lookup key into the store's `byPosition` map; the shell drives the
   * windowed fetch that fills it. Pass either this or `rom`, not both. */
  position?: number;
  /** Static ROM data — used by non-gallery surfaces (Settings → Missing
   * games) that already own the rom list. When provided, the row skips
   * the galleryRoms position lookup. */
  rom?: SimpleRom | null;
  /** Cover variant — when the browser supports webp the thumb URL is
   * rewritten to .webp before the request. Wired from the shell so the
   * choice is decided once per gallery render, not per row. */
  webp?: boolean;
  /** Include the `platform` column. Mirrors `GameListHeader` so the row
   * stays aligned with the column header above it. */
  showPlatformColumn?: boolean;
  /** Offer the chevron that opens the detail panel (phones and tablets).
   * Only for surfaces whose virtualiser reserves the taller row. */
  expandable?: boolean;
  /** Whether this row's detail panel is open. */
  expanded?: boolean;
  /** Px of that panel currently showing; it rolls open and shut. */
  detailHeight?: number;
}

const props = withDefaults(defineProps<Props>(), {
  position: undefined,
  rom: undefined,
  webp: false,
  showPlatformColumn: true,
  expandable: false,
  expanded: false,
  detailHeight: 0,
});

const emit = defineEmits<{
  /** Forwards the cover's measured natural ratio so the shell's flow-packer
   *  can pack the grid by true cover shape. */
  (e: "ratio", payload: { romId: number; ratio: number }): void;
  /** Chevron pressed; the parent owns which row is open. */
  (e: "toggle-expand"): void;
}>();

const router = useRouter();
const galleryRoms = storeGalleryRoms();
const selection = storeGallerySelection();
const selectionInput = useGallerySelectionInput();
const platformsStore = storePlatforms();
const collectionsStore = storeCollections();
const { morphTransition } = useViewTransition();
const setBgArt = useBackgroundArt();
const { locale, t } = useI18n();

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
const titleSkeletonGapStyle = { gap: `${LIST_TITLE_SKELETON_GAP_PX}px` };

/** The panel's fields after the file name, in the order it lays them out:
 *  the size beside the name, then two rows of three. */
const detailFields = computed(() => {
  const item = rom.value;
  if (!item) return [];
  return [
    { label: labelOf("fs_size_bytes"), value: formatBytes(item.fs_size_bytes) },
    { label: labelOf("created_at"), value: formatDate(item.created_at) },
    { label: labelOf("first_release_date"), value: releaseDate(item) },
    { label: labelOf("hltb_main_story"), value: lengthValue(item) },
    { label: labelOf("average_rating"), value: ratingValue(item) },
    { label: labelOf("languages"), value: listValue(item.languages) },
    { label: labelOf("regions"), value: listValue(item.regions) },
  ];
});

/** Alignment / figure modifiers for a cell, read off the column config so
 *  the body cannot drift from the header above it. */
function cellModifiers(key: ListColumn["key"]) {
  const column = columns.value.find((col) => col.key === key);
  return {
    "game-list-row__cell--end": column?.align === "end",
    "game-list-row__cell--num": column?.numeric === true,
  };
}

// Phones and tablets have no room for the columns: the row collapses to a
// title plus the facts line, and the rest moves into the detail panel.
const { smAndDown } = useBreakpoint();

const rowEl = ref<HTMLElement | null>(null);
const { entranceClass, entranceStyle, endEntrance } = useStaggeredEntrance(
  rowEl,
  () => rom.value != null,
);

/** Column header label, so the detail panel's captions and the desktop
 *  column titles can't drift apart. */
function labelOf(key: ListColumn["key"]): string {
  return columns.value.find((col) => col.key === key)?.label ?? "";
}

function listValue(values: string[] | null | undefined): string {
  return values && values.length > 0 ? values.join(", ") : "—";
}

/** Leads the facts line wherever the list mixes platforms. */
const platformName = computed(() => {
  const item = rom.value;
  if (!item || !props.showPlatformColumn) return null;
  return item.platform_custom_name || item.platform_display_name;
});

const year = computed(() =>
  releaseYear(rom.value?.metadatum?.first_release_date),
);

const isFavorited = computed(() =>
  rom.value ? collectionsStore.isFavorite(rom.value) : false,
);

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
  return (
    formatReleaseDate(
      item.metadatum?.first_release_date,
      toBrowserLocale(locale.value),
    ) ?? "—"
  );
}

function ratingValue(item: SimpleRom): string {
  const r = item.metadatum?.average_rating;
  if (typeof r !== "number" || r <= 0) return "—";
  return r.toFixed(1);
}

function lengthValue(item: SimpleRom): string {
  return (
    formatPlaytime(
      item.hltb_metadata?.main_story,
      toBrowserLocale(locale.value),
    ) ?? "—"
  );
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

// Mirror of GameCard's onHighlight: swap the AppLayout backdrop to the
// hovered/focused row's cover. Skipped in static mode (non-gallery
// surfaces like Settings → Missing games don't drive a backdrop).
function onRowHighlight() {
  if (isStatic.value) return;
  const item = rom.value;
  if (!item) return;
  const path = item.path_cover_large ?? item.path_cover_small ?? null;
  const coverUrl = path ? toWebpUrl(path, !!props.webp) : null;
  if (coverUrl) setBgArt(coverUrl);
  else if (item.url_cover) setBgArt(item.url_cover);
}

function onRowPointerDown(e: PointerEvent) {
  const item = rom.value;
  if (!item || isStatic.value || props.position === undefined) return;
  // Reading the open panel is not a press on the row.
  if ((e.target as Element | null)?.closest(".game-list-row__detail")) return;
  selectionInput.handlePointerDown(item, props.position, e);
}
</script>

<template>
  <a
    ref="rowEl"
    class="game-list-row"
    :class="[
      {
        'game-list-row--columns': !smAndDown,
        'game-list-row--clickable': !!rom,
        'game-list-row--selected': isSelected,
        'game-list-row--expanded': expanded,
      },
      entranceClass,
    ]"
    :style="[smAndDown ? undefined : gridStyle, entranceStyle]"
    :href="rom ? `/rom/${rom.id}` : undefined"
    :aria-label="
      rom
        ? t('common.open-item', { name: rom.name ?? rom.fs_name_no_ext })
        : undefined
    "
    :data-rom-position="position"
    :data-rom-id="rom?.id"
    :data-focus-key="rom ? `rom-${rom.id}` : undefined"
    @click="onRowClick"
    @mouseenter="onRowHighlight"
    @focus="onRowHighlight"
    @pointerdown="onRowPointerDown"
    @contextmenu="selectionInput.handleContextMenu"
    @animationend.self="endEntrance"
  >
    <template v-if="rom">
      <!-- COMPACT (phones / tablets): two lines plus the chevron; the
           columns move into the detail panel below. -->
      <template v-if="smAndDown">
        <div class="game-list-row__compact r-list-compact">
          <div class="game-list-row__select">
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

          <div class="game-list-row__cover">
            <GameCard
              :rom="rom"
              size="xs"
              :webp="webp"
              decorative
              :show-title="false"
              :show-platform-icon="showPlatformColumn"
              @ratio="emit('ratio', $event)"
            />
          </div>

          <div class="r-list-compact__stack">
            <div class="game-list-row__name">
              {{ rom.name ?? rom.fs_name_no_ext }}
            </div>
            <div class="r-list-compact__facts">
              <template v-if="platformName">
                <RPlatformIcon
                  class="game-list-row__facts-icon"
                  :slug="rom.platform_slug"
                  :fs-slug="rom.platform_fs_slug"
                  :alt="platformName"
                  :size="14"
                  :show-tooltip="false"
                />
                <span>{{ platformName }}</span>
              </template>
              <span v-if="platformName && year" class="r-list-compact__dot"
                >·</span
              >
              <span v-if="year">{{ year }}</span>
              <template v-if="isFavorited">
                <span v-if="platformName || year" class="r-list-compact__dot"
                  >·</span
                >
                <RIcon
                  icon="mdi-heart"
                  size="11"
                  class="game-list-row__fav"
                  :aria-label="t('rom.favorite')"
                />
              </template>
            </div>
            <div class="game-list-row__badges" @click.stop>
              <GameActionBtn
                v-if="hasStatus"
                :rom="rom"
                action="status"
                size="x-small"
                variant="surface"
                orientation="horizontal"
              />
              <SiblingBadge :rom="rom" orientation="horizontal" />
            </div>
          </div>

          <div class="game-list-row__actions" @click.stop>
            <GameActionBtn
              :rom="rom"
              action="more"
              size="small"
              variant="bare"
            />
            <button
              v-if="expandable"
              type="button"
              class="game-list-row__chevron"
              :class="{ 'game-list-row__chevron--open': expanded }"
              :aria-expanded="expanded"
              :aria-label="t('common.details')"
              @click.stop.prevent="emit('toggle-expand')"
            >
              <RIcon icon="mdi-chevron-down" size="18" />
            </button>
          </div>
        </div>

        <div
          v-if="expanded"
          class="game-list-row__detail"
          :style="{ height: `${detailHeight}px` }"
          @click.stop
        >
          <div class="game-list-row__detail-inner">
            <div class="game-list-row__field game-list-row__field--filename">
              <span class="game-list-row__field-label">{{
                t("rom.filename")
              }}</span>
              <RMarquee class="game-list-row__field-value">{{
                rom.fs_name
              }}</RMarquee>
            </div>
            <div
              v-for="field in detailFields"
              :key="field.label"
              class="game-list-row__field"
            >
              <span class="game-list-row__field-label">{{ field.label }}</span>
              <span class="game-list-row__field-value">{{ field.value }}</span>
            </div>
            <div class="game-list-row__field game-list-row__field--wide">
              <span class="game-list-row__field-label">{{
                t("scan.metadata-sources")
              }}</span>
              <ProviderBadges
                v-if="providers.length > 0"
                :providers="providers"
              />
              <span v-else class="game-list-row__field-value">—</span>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <!-- Selection cell, leftmost column. Click toggles this row;
           shift-click extends the range from the last toggled position.
           Hidden at rest; reveals on row hover / focus or whenever the
           row is selected so the user always knows which rows are
           picked. RCheckbox provides the box / fill / draw animations
           (same animation language as the GameCard checkbox in grid
           mode). -->
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

        <div class="game-list-row__cell game-list-row__cover">
          <GameCard
            :rom="rom"
            size="xs"
            :webp="webp"
            decorative
            :show-title="false"
            :show-platform-icon="false"
            @ratio="emit('ratio', $event)"
          />
        </div>

        <div class="game-list-row__cell game-list-row__title">
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
            <ProviderBadges
              v-if="providers.length > 0"
              class="game-list-row__providers"
              :providers="providers"
              @click.stop
            />
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

        <div
          class="game-list-row__cell"
          :class="cellModifiers('fs_size_bytes')"
        >
          {{ formatBytes(rom.fs_size_bytes) }}
        </div>
        <div class="game-list-row__cell" :class="cellModifiers('created_at')">
          {{ formatDate(rom.created_at) }}
        </div>
        <div
          class="game-list-row__cell"
          :class="cellModifiers('first_release_date')"
        >
          {{ releaseDate(rom) }}
        </div>
        <div
          class="game-list-row__cell"
          :class="cellModifiers('average_rating')"
        >
          {{ ratingValue(rom) }}
        </div>
        <div
          class="game-list-row__cell"
          :class="cellModifiers('hltb_main_story')"
        >
          {{ lengthValue(rom) }}
        </div>

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

        <div class="game-list-row__cell" :class="cellModifiers('actions')">
          <div class="game-list-row__actions" @click.stop>
            <GameActionBtn
              :rom="rom"
              action="favorite"
              size="small"
              variant="bare"
            />
            <GameActionBtn
              :rom="rom"
              action="more"
              size="small"
              variant="bare"
            />
          </div>
        </div>
      </template>
    </template>

    <template v-else>
      <!-- Compact skeleton, same two-line shape as the compact row. -->
      <div v-if="smAndDown" class="game-list-row__compact r-list-compact">
        <div class="game-list-row__select" />
        <div class="game-list-row__cover">
          <RSkeletonBlock
            :width="LIST_COVER_WIDTH_PX"
            :height="LIST_COVER_HEIGHT_PX"
          />
        </div>
        <div class="r-list-compact__stack" :style="titleSkeletonGapStyle">
          <RSkeletonBlock
            v-for="(bar, i) in LIST_TITLE_SKELETON_BARS"
            :key="i"
            :width="bar.width"
            :height="bar.height"
          />
        </div>
      </div>

      <!-- Column-driven, so the per-cell shapes stay in step with
           `GameListSkeletonRow` and the row does not reflow on data arrival. -->
      <template v-else>
        <template v-for="col in listSkeletonColumns" :key="String(col.key)">
          <div
            v-if="col.key === 'select'"
            class="game-list-row__cell game-list-row__select"
          >
            <!-- Empty cell during skeleton phase, no placeholder so the
               selection chrome only appears once a real row exists. -->
          </div>
          <div
            v-else-if="col.key === 'cover'"
            class="game-list-row__cell game-list-row__cover"
          >
            <RSkeletonBlock
              :width="LIST_COVER_WIDTH_PX"
              :height="LIST_COVER_HEIGHT_PX"
            />
          </div>
          <div
            v-else-if="col.key === 'name'"
            class="game-list-row__cell game-list-row__title"
          >
            <div class="game-list-row__meta" :style="titleSkeletonGapStyle">
              <RSkeletonBlock
                v-for="(bar, i) in LIST_TITLE_SKELETON_BARS"
                :key="i"
                :width="bar.width"
                :height="bar.height"
              />
            </div>
          </div>
          <div
            v-else-if="col.key === 'platform_id'"
            class="game-list-row__cell"
          >
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
            class="game-list-row__cell"
            :class="cellModifiers('actions')"
          >
            <RSkeletonBlock :width="18" :height="18" circle />
          </div>
          <div
            v-else
            class="game-list-row__cell"
            :class="{ 'game-list-row__cell--end': col.align === 'end' }"
          >
            <RSkeletonBlock :width="col.skeletonWidth ?? 60" :height="10" />
          </div>
        </template>
      </template>
    </template>
  </a>
</template>

<style scoped>
.game-list-row {
  /* An inline <a> would shrink-wrap its content and swallow the bleed. */
  display: block;
  /* The long press selects the row; iOS would offer its link callout too. */
  -webkit-touch-callout: none;
  /* Runs to the screen edges wherever the shell asks for it. */
  margin-inline: calc(-1 * var(--r-list-bleed, 0px));
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  cursor: default;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

/* Column layout, for the viewports that still have columns. The compact
   branch is plain flow, so it needs nothing cancelled. */
.game-list-row--columns {
  display: grid;
  align-items: center;
  gap: 0 var(--r-space-5);
  /* Runs to the leading screen edge wherever the shell asks, keeping that
     gutter as padding so the first column lines up with the toolbar. */
  margin-inline-start: calc(-1 * var(--r-list-bleed-start, 0px));
  padding: 0 var(--r-space-3);
  padding-inline-start: max(var(--r-space-3), var(--r-list-bleed-start, 0px));
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
}

/* ── Compact layout (phones / tablets) ───────────────────────────────
   No columns: a two-line block, and a detail panel whose fixed height the
   virtualiser mirrors (`LIST_ROW_DETAIL_HEIGHT_PX`) so the rows below an
   open row sit clear of it. */
.game-list-row__compact {
  height: var(--r-list-row-h);
  border-bottom: 1px solid var(--r-color-border);
}
.game-list-row--expanded .game-list-row__compact {
  border-bottom-color: transparent;
}
.game-list-row__compact > .game-list-row__select {
  flex: none;
  width: var(--r-list-select-w);
}
/* Two lines of title: most names fit whole, and the row keeps its height
   (cover 64 + two lines + the facts line still sit inside it). */
.game-list-row__compact .game-list-row__name {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  white-space: normal;
  line-height: 1.25;
}
.game-list-row__facts-icon,
.game-list-row__fav {
  flex-shrink: 0;
}
.game-list-row__fav {
  color: var(--r-color-brand-primary);
}

.game-list-row__chevron {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 4px;
  display: inline-flex;
  align-items: center;
  color: var(--r-color-fg-muted);
  cursor: pointer;
  transition: transform var(--r-motion-fast) var(--r-motion-ease-out);
}
.game-list-row__chevron--open {
  transform: rotate(180deg);
  color: var(--r-color-fg);
}
/* Rolls open and shut: the height comes from `useListExpansion`, which the
   virtualiser reads too, so the panel and the slot it sits in move together.
   The inner block keeps its full height and is clipped meanwhile. */
.game-list-row__detail {
  overflow: hidden;
  border-bottom: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
  cursor: default;
}
.game-list-row__detail-inner {
  height: var(--r-list-row-detail-h);
  padding: var(--r-space-4) var(--r-row-pad);
  display: grid;
  /* Three equal columns across the full width, so the fields land in the
     same place whatever the title or the file name measure. */
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--r-space-4);
  align-content: start;
}
.game-list-row__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
/* One line, always: the panel's height is fixed (`--r-list-row-detail-h`) for
   the virtualiser, so a caption that wraps in another locale would push the
   last field out of the clipped box. */
.game-list-row__field-label {
  font-size: var(--r-font-size-xs);
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.game-list-row__field--wide {
  grid-column: 1 / -1;
}
/* Loops sideways when it overflows, so a long name reads whole in one line. */
.game-list-row__field--filename {
  grid-column: span 2;
}
.game-list-row__field-value {
  font-size: var(--r-font-size-md);
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

/* The scroller clips an outline past the row's screen edge, so key and pad
   focus paint inside the row. */
html:not([data-input]) .game-list-row:focus-visible,
html[data-input="key"] .game-list-row:focus-visible,
html[data-input="pad"] .game-list-row:focus-visible {
  outline: none;
  box-shadow: inset 0 0 0 var(--r-focus-ring-width) var(--r-color-focus);
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

/* Quantities and dates pin to the column's right edge, so the digits line up
   down the column instead of stepping with the unit or month width. */
.game-list-row__cell--end {
  text-align: end;
}

/* Tabular figures for the digit columns: proportional digits make the
   column ragged even at a fixed width. */
.game-list-row__cell--num {
  font-variant-numeric: tabular-nums;
}

/* Cover sits in its own fixed-width column (centred) so the title/meta
   column starts at the same x on every row. */
.game-list-row__cover {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Bound the xs cover to its fixed column: at the fixed xs height a wide
   (landscape) cover would render wider than the column and spill out, getting
   clipped on the left. Cap the art box to a square (max-width = the height)
   and let the cover letterbox (contain) within, so the whole cover still
   shows at its true aspect. Portrait/square covers are unaffected (their
   natural width already fits, and contain renders identically to cover when
   the box matches the cover's ratio). Scoped to the list cover only — the
   gallery grid keeps its natural-width flow. */
.game-list-row__cover :deep(.r-gc__art) {
  max-width: var(--r-card-art-h);
}
.game-list-row__cover :deep(.r-gc__art > img) {
  object-fit: contain !important;
}

.game-list-row__title {
  display: flex;
  align-items: center;
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

/* The badges own their look; the column layout only adds the gap under the
   file name above them. */
.game-list-row__providers {
  margin-top: 4px;
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
