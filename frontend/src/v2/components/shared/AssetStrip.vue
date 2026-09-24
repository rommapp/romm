<script setup lang="ts">
// Tile strip or grid of saves/states, shared by the launch screens (selection)
// and the Save data subtab (management). `groupBy` folds the tiles per core.
import {
  RCheckbox,
  REmptyState,
  RExpandTransition,
  RIcon,
  RTag,
} from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useStreamingStore } from "@/stores/streaming";
import AssetChips from "@/v2/components/shared/AssetChips.vue";
import AssetFavoriteMark from "@/v2/components/shared/AssetFavoriteMark.vue";
import AssetGroupHead from "@/v2/components/shared/AssetGroupHead.vue";
import AssetLabels from "@/v2/components/shared/AssetLabels.vue";
import AssetOwnerChip from "@/v2/components/shared/AssetOwnerChip.vue";
import AssetTimestamp from "@/v2/components/shared/AssetTimestamp.vue";
import { useGroupFold } from "@/v2/composables/useGroupFold";
import {
  byFavoriteFirst,
  emulatorKey,
  ownerOf,
  screenshotOf,
  staggerIndex,
  type Asset,
  type AssetType,
} from "@/v2/utils/assets";
import { toCssUrl } from "@/v2/utils/css";

defineOptions({ inheritAttrs: false });

export type AssetLayout = "strip" | "flow" | "grid" | "list";

const props = withDefaults(
  defineProps<{
    assets: Asset[];
    type: AssetType;
    selectable?: boolean;
    selectedId?: number | null;
    showOwner?: boolean;
    layout?: AssetLayout;
    /** Why an asset cannot be picked here; a reason disables its tile. */
    disabledReason?: (asset: Asset) => string | null;
    groupBy?: "emulator";
    /** Manage mode: lead each tile with a checkbox for bulk actions. Distinct
     *  from `selectable`, which is the player's single-asset picker. */
    checkable?: boolean;
    checkedIds?: ReadonlySet<number>;
  }>(),
  {
    selectable: true,
    selectedId: null,
    showOwner: false,
    layout: "strip",
    disabledReason: undefined,
    groupBy: undefined,
    checkable: false,
    checkedIds: () => new Set<number>(),
  },
);

defineEmits<{
  select: [asset: Asset];
  toggle: [asset: Asset];
}>();

defineSlots<{
  actions(props: { asset: Asset }): unknown;
}>();

const { t } = useI18n();
const { emulatorLabel } = useStreamingStore();

const emptyLabel = computed(() =>
  props.type === "save"
    ? t("play.no-saves-available")
    : t("play.no-states-available"),
);

function reasonOf(asset: Asset): string | null {
  return props.selectable ? (props.disabledReason?.(asset) ?? null) : null;
}

interface AssetGroup {
  key: string;
  label: string;
  /** Favorites first, then source order, so a newest-first list reads top-left. */
  assets: Asset[];
  /** Every tile disabled: nothing in this group can be picked. */
  disabled: boolean;
  newest: string;
  /** The tile tagged "Latest": first in source order among the newest. */
  newestId: number | null;
}

const groups = computed<AssetGroup[]>(() => {
  if (props.assets.length === 0) return [];
  if (!props.groupBy) {
    return [
      {
        key: "all",
        label: "",
        assets: [...props.assets].sort(byFavoriteFirst),
        disabled: false,
        newest: "",
        newestId: null,
      },
    ];
  }
  const byKey = new Map<string, AssetGroup>();
  for (const asset of props.assets) {
    const key = emulatorKey(asset.emulator);
    let group = byKey.get(key);
    if (!group) {
      group = {
        key,
        label: emulatorLabel(asset.emulator) || t("play.any-core"),
        assets: [],
        disabled: true,
        newest: "",
        newestId: null,
      };
      byKey.set(key, group);
    }
    group.assets.push(asset);
    if (!reasonOf(asset)) group.disabled = false;
    if (asset.updated_at > group.newest) {
      group.newest = asset.updated_at;
      group.newestId = asset.id;
    }
  }
  const list = [...byKey.values()];
  for (const group of list) group.assets.sort(byFavoriteFirst);
  return list.sort(
    (a, b) =>
      Number(a.disabled) - Number(b.disabled) ||
      b.newest.localeCompare(a.newest),
  );
});

// Loadable groups start open; a group opens when it takes the selection.
const fold = useGroupFold<AssetGroup>({
  groups,
  keyOf: (group) => group.key,
  holdsSelection: (group) =>
    props.selectable &&
    group.assets.some((asset) => asset.id === props.selectedId),
  defaultOpen: (group) => !group.disabled,
  selectedId: () => props.selectedId,
});
function isOpen(group: AssetGroup): boolean {
  return !props.groupBy || fold.isOpen(group);
}

const fadeIndex = computed(() =>
  staggerIndex(
    groups.value.map((group) => (isOpen(group) ? group.assets : [])),
  ),
);
</script>

<template>
  <div
    class="r-asset-strip"
    :class="[`r-asset-strip--${layout}`, { 'r-asset-strip--grouped': groupBy }]"
  >
    <div v-for="group in groups" :key="group.key" class="r-asset-strip__group">
      <AssetGroupHead
        v-if="groupBy"
        icon="mdi-chip"
        icon-tone="warning"
        :title="group.label"
        :muted="group.disabled"
        :count="group.assets.length"
        foldable
        :expanded="isOpen(group)"
        @toggle="fold.toggle(group)"
      >
        <RTag
          v-if="group.disabled"
          tone="neutral"
          size="x-small"
          :text="t('play.core-not-loadable')"
        />
      </AssetGroupHead>

      <RExpandTransition>
        <div v-show="isOpen(group)" class="r-asset-strip__fold">
          <div class="r-asset-strip__track">
            <component
              :is="selectable ? 'button' : 'div'"
              v-for="asset in group.assets"
              :key="asset.id"
              :type="selectable ? 'button' : undefined"
              class="r-asset-strip__tile r-v2-asset-fade"
              :class="{
                'r-asset-strip__tile--active':
                  selectable && asset.id === selectedId,
                'r-asset-strip__tile--static': !selectable,
                'r-asset-strip__tile--disabled': reasonOf(asset),
                'r-asset-strip__tile--checked':
                  checkable && checkedIds.has(asset.id),
              }"
              :style="{ '--asset-fade-i': fadeIndex.get(asset.id) }"
              :aria-pressed="selectable ? asset.id === selectedId : undefined"
              :aria-disabled="reasonOf(asset) ? true : undefined"
              @click="selectable && !reasonOf(asset) && $emit('select', asset)"
            >
              <div v-if="layout !== 'list'" class="r-asset-strip__thumb">
                <div
                  v-if="type === 'state' && screenshotOf(asset)"
                  class="r-asset-strip__thumb-img"
                  :style="{ backgroundImage: toCssUrl(screenshotOf(asset)!) }"
                />
                <div v-else class="r-asset-strip__thumb-icon">
                  <RIcon
                    :icon="
                      type === 'save' ? 'mdi-content-save' : 'mdi-file-outline'
                    "
                    size="28"
                  />
                </div>
                <AssetFavoriteMark
                  class="r-asset-strip__fav"
                  :favorite="selectable && asset.is_favorite"
                  :size="14"
                />
              </div>
              <div class="r-asset-strip__body">
                <div class="r-asset-strip__meta">
                  <p class="r-asset-strip__name">
                    <span class="r-asset-strip__name-text">
                      {{ asset.file_name }}
                    </span>
                    <!-- The list layout has no thumbnail to ride. -->
                    <AssetFavoriteMark
                      v-if="layout === 'list'"
                      :favorite="selectable && asset.is_favorite"
                      :size="13"
                    />
                  </p>
                  <AssetLabels :asset="asset" />
                  <AssetChips
                    :asset="asset"
                    :latest="
                      !!groupBy &&
                      group.assets.length > 1 &&
                      asset.id === group.newestId
                    "
                    :show-emulator="!groupBy && type === 'state'"
                  />
                  <AssetTimestamp
                    :date="asset.updated_at"
                    :stacked="layout === 'list'"
                    class="r-asset-strip__time"
                  />
                  <AssetOwnerChip
                    v-if="showOwner && ownerOf(asset)"
                    :owner="ownerOf(asset)!"
                    :size="14"
                    class="r-asset-strip__owner"
                  />
                </div>
                <div v-if="!selectable" class="r-asset-strip__actions">
                  <span v-if="checkable" class="r-asset-strip__check">
                    <RCheckbox
                      :model-value="checkedIds.has(asset.id)"
                      size="sm"
                      hide-details
                      bare
                      :aria-label="
                        t('rom.select-asset', { name: asset.file_name })
                      "
                      @update:model-value="$emit('toggle', asset)"
                    />
                  </span>
                  <slot name="actions" :asset="asset" />
                </div>
              </div>
            </component>
          </div>
        </div>
      </RExpandTransition>
    </div>

    <REmptyState
      v-if="assets.length === 0"
      size="small"
      :icon="type === 'save' ? 'mdi-content-save-outline' : 'mdi-file-outline'"
      :icon-size="28"
      :title="emptyLabel"
    />
  </div>
</template>

<style scoped>
.r-asset-strip {
  width: 100%;
}

/* ── Groups (groupBy) ────────────────────────────────────── */
.r-asset-strip--grouped {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.r-asset-strip__group {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
/* Each core sits on its own neutral band, so the gaps between sections
   read as separators. */
.r-asset-strip--grouped .r-asset-strip__group {
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}
.r-asset-strip--grouped .r-asset-strip__fold {
  padding: 0 8px 8px;
}
.r-asset-strip__track {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-snap-type: x proximity;
  padding: 4px 2px 10px;
  scrollbar-color: var(--r-color-border-strong) transparent;
  scrollbar-width: thin;
}
.r-asset-strip__track::-webkit-scrollbar {
  height: 6px;
}
.r-asset-strip__track::-webkit-scrollbar-track {
  background: transparent;
}
.r-asset-strip__track::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 6px;
}

/* Flow layout: a responsive grid with cells wide enough that labels and chips
   don't stack a tile too tall. min() lets a lone column shrink on a phone. */
.r-asset-strip--flow .r-asset-strip__track {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(260px, 100%), 1fr));
  overflow: visible;
  scroll-snap-type: none;
  padding: 4px 0;
}
.r-asset-strip--flow .r-asset-strip__tile {
  scroll-snap-align: none;
}

/* Grid layout: the strip's tiles in a capped, vertically scrolling box.
   Column count is fixed rather than auto-fill so tile size stays predictable
   next to the preview pane. */
.r-asset-strip--grid .r-asset-strip__track {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow-x: hidden;
  overflow-y: auto;
  max-height: 340px;
  scroll-snap-type: none;
  padding: 4px 2px;
}
.r-asset-strip--grid .r-asset-strip__tile {
  flex: initial;
  scroll-snap-align: none;
}

/* List layout: no thumbnail; name, chips, owner and timestamp share one row,
   the timestamp last on a fixed width so its right edge lines up. */
.r-asset-strip--list .r-asset-strip__track {
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow-x: hidden;
  overflow-y: auto;
  max-height: 340px;
  scroll-snap-type: none;
  padding: 2px;
}
.r-asset-strip--list .r-asset-strip__tile {
  border-width: 0;
  flex: initial;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 5px 8px;
  border-radius: var(--r-radius-sm);
  scroll-snap-align: none;
  text-align: left;
}
.r-asset-strip--list .r-asset-strip__tile:hover {
  transform: none;
  background: var(--r-color-surface-hover);
}
.r-asset-strip--list .r-asset-strip__tile--active,
.r-asset-strip--list .r-asset-strip__tile--active:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
}
.r-asset-strip--list .r-asset-strip__meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  padding: 0;
}
.r-asset-strip--list .r-asset-strip__name {
  flex: 1;
  min-width: 0;
}
.r-asset-strip--list .r-asset-strip__time {
  order: 1;
  flex: 0 0 96px;
}
.r-asset-strip--list .r-asset-strip__owner {
  flex: 0 0 auto;
  margin-top: 0;
  max-width: 120px;
}

.r-asset-strip__tile {
  appearance: none;
  /* Same resting, hover and selected border as the save rows. */
  border: 1px solid var(--r-color-border);
  background: transparent;
  padding: 0;
  flex: 0 0 140px;
  /* Without min-width:0 the flex item's implicit `min-width: auto`
     lets the inner nowrap filename push the tile wider than its
     flex-basis — long names would visibly inflate that one card. */
  min-width: 0;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  text-align: left;
  cursor: pointer;
  border-radius: var(--r-radius-md);
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
/* The entrance animation sits on the tile itself, so its final frame would
   pin the transform; releasing the fill lets the hover lift through. */
.r-asset-strip__tile.r-v2-asset-fade {
  animation-fill-mode: backwards;
}
.r-asset-strip__tile:hover {
  transform: translateY(-1px);
  border-color: var(--r-color-border-strong);
  background: var(--r-color-surface);
}
.r-asset-strip__tile--active,
.r-asset-strip__tile--active:hover {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}
.r-asset-strip__tile:active {
  transform: translateY(0);
}
/* Manage mode: tiles are static info cards, not selectable buttons. */
.r-asset-strip__tile--static {
  cursor: default;
}
.r-asset-strip__tile--static:hover {
  transform: none;
  border-color: var(--r-color-border);
  background: transparent;
}
/* Kept visible so the count adds up; the tooltip carries the reason. */
.r-asset-strip__tile--disabled {
  cursor: not-allowed;
  filter: grayscale(1);
  opacity: 0.6;
}
.r-asset-strip__tile--disabled:hover {
  transform: none;
  border-color: var(--r-color-border);
  background: transparent;
}

/* One card: the screenshot fills the top, the tinted body sits flush below. */
.r-asset-strip__thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: calc(var(--r-radius-md) - 1px) calc(var(--r-radius-md) - 1px) 0
    0;
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
}

.r-asset-strip__thumb-img {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
}
.r-asset-strip__thumb-icon {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--r-color-fg-muted);
  background: linear-gradient(
    135deg,
    var(--r-color-cover-placeholder),
    var(--r-color-cover-placeholder-bright)
  );
}

/* Top left, matching the state preview's stage. */
.r-asset-strip__fav {
  position: absolute;
  top: 4px;
  left: 6px;
  filter: drop-shadow(0 1px 3px color-mix(in srgb, black 75%, transparent));
}
.r-asset-strip__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 8px 8px 10px;
  border-radius: 0 0 calc(var(--r-radius-md) - 1px)
    calc(var(--r-radius-md) - 1px);
  background: color-mix(in srgb, var(--r-color-fg) 5%, transparent);
}
.r-asset-strip--list .r-asset-strip__body {
  display: contents;
}

.r-asset-strip__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.r-asset-strip__name {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  overflow-wrap: anywhere;
}
/* One line with the heart pinned beside it: only the text truncates, so the
   mark survives a long filename. */
.r-asset-strip--list .r-asset-strip__name {
  display: flex;
  align-items: center;
  gap: 6px;
}
.r-asset-strip--list .r-asset-strip__name-text {
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-strip__tile--active .r-asset-strip__name {
  color: var(--r-color-brand-primary);
}

/* Author chip on community tiles: avatar + username. */
.r-asset-strip__owner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  min-width: 0;
}
.r-asset-strip__owner > span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Manage mode: action buttons under the tile meta. */
.r-asset-strip__actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
}
.r-asset-strip__check {
  display: inline-flex;
  align-items: center;
  margin-right: auto;
}
/* The `--static` hover reset outranks a single class, so it is listed too. */
.r-asset-strip__tile--checked,
.r-asset-strip__tile--checked:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 10%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 40%,
    transparent
  );
}

html[data-bp~="xs"] .r-asset-strip__tile {
  flex: 0 0 120px;
}
html[data-bp~="xs"] .r-asset-strip--grid .r-asset-strip__track {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
</style>
