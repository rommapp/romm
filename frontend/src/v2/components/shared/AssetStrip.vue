<script setup lang="ts">
// Strip / grid of save/state tiles. Shared between the EmulatorJS pre-game
// view (selection) and the GameDetails "Save data" subtab (management).
//
// State tiles show their 16:9 screenshot prominently; saves fall back
// to a large save icon. The currently-selected tile gets a brand-color
// ring + check badge so it reads as "you're about to resume from this
// one". Hovering lifts the tile; tiles are focusable for gamepad/key
// navigation.
//
// Layout (`wrap`):
//   * strip (default) — Play view. Single horizontal row, scroll + snap,
//     never wraps; tiles shrink on narrow screens.
//   * wrap — Save data subtab. Tiles flow into a responsive grid.
//
// Modes (`selectable`):
//   * selectable (default) — tiles are buttons; clicking emits `select`;
//     the chosen tile gets a brand ring + check badge.
//   * manage (selectable=false) — tiles are static; the `#actions` slot
//     renders below the meta, and `showOwner` adds an author chip.
import { RAvatar, RIcon, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type {
  SaveSchema,
  StateSchema,
  UserSaveSchema,
  UserStateSchema,
} from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";
type Asset = SaveSchema | StateSchema | UserSaveSchema | UserStateSchema;

const props = withDefaults(
  defineProps<{
    assets: Asset[];
    type: AssetType;
    selectable?: boolean;
    selectedId?: number | null;
    showOwner?: boolean;
    /** Flow tiles into a responsive grid instead of a single scroll row. */
    wrap?: boolean;
  }>(),
  {
    selectable: true,
    selectedId: null,
    showOwner: false,
    wrap: false,
  },
);

defineEmits<{
  select: [asset: Asset];
}>();

defineSlots<{
  actions(props: { asset: Asset }): unknown;
}>();

const { t, locale } = useI18n();

const emptyLabel = computed(() =>
  props.type === "save"
    ? t("play.no-saves-available")
    : t("play.no-states-available"),
);

function screenshotOf(asset: Asset): string | null {
  if ("screenshot" in asset && asset.screenshot?.download_path) {
    return asset.screenshot.download_path;
  }
  return null;
}

function ownerOf(asset: Asset): UserSaveSchema | UserStateSchema | null {
  return "username" in asset && asset.username ? asset : null;
}
</script>

<template>
  <div class="r-asset-strip" :class="{ 'r-asset-strip--wrap': wrap }">
    <div v-if="assets.length > 0" class="r-asset-strip__track">
      <component
        :is="selectable ? 'button' : 'div'"
        v-for="(asset, i) in assets"
        :key="asset.id"
        :type="selectable ? 'button' : undefined"
        class="r-asset-strip__tile r-v2-asset-fade"
        :class="{
          'r-asset-strip__tile--active': selectable && asset.id === selectedId,
          'r-asset-strip__tile--static': !selectable,
        }"
        :style="{ '--asset-fade-i': i }"
        :aria-pressed="selectable ? asset.id === selectedId : undefined"
        @click="selectable && $emit('select', asset)"
      >
        <div class="r-asset-strip__thumb">
          <div
            v-if="type === 'state' && screenshotOf(asset)"
            class="r-asset-strip__thumb-img"
            :style="{ backgroundImage: `url(${screenshotOf(asset)})` }"
          />
          <div v-else class="r-asset-strip__thumb-icon">
            <RIcon
              :icon="type === 'save' ? 'mdi-content-save' : 'mdi-file-outline'"
              size="28"
            />
          </div>
          <span
            v-if="selectable && asset.id === selectedId"
            class="r-asset-strip__check"
            aria-hidden="true"
          >
            <RIcon icon="mdi-check" size="14" />
          </span>
        </div>
        <div class="r-asset-strip__meta">
          <p class="r-asset-strip__name">
            {{ asset.file_name }}
          </p>
          <p class="r-asset-strip__sub">
            <span>{{ formatRelativeDate(asset.updated_at) }}</span>
            <span class="r-asset-strip__dot" aria-hidden="true">·</span>
            <span>{{ formatBytes(asset.file_size_bytes) }}</span>
          </p>
          <span v-if="showOwner && ownerOf(asset)" class="r-asset-strip__owner">
            <RAvatar
              :image="
                userAvatarUrl(
                  ownerOf(asset)!.user_id,
                  ownerOf(asset)!.user_avatar_path,
                  ownerOf(asset)!.user_updated_at,
                )
              "
              :size="14"
            />
            <span>{{ ownerOf(asset)!.username }}</span>
          </span>
        </div>
        <div v-if="!selectable" class="r-asset-strip__actions">
          <slot name="actions" :asset="asset" />
        </div>
        <RTooltip
          v-if="selectable"
          activator="parent"
          location="top"
          :open-delay="400"
        >
          <div class="r-asset-strip__tip">
            <span class="r-asset-strip__tip-name">{{ asset.file_name }}</span>
            <span class="r-asset-strip__tip-sub">
              {{ t("rom.updated") }}:
              {{ formatTimestamp(asset.updated_at, locale) }}
            </span>
          </div>
        </RTooltip>
      </component>
    </div>

    <div v-else class="r-asset-strip__empty">
      <RIcon
        :icon="
          type === 'save' ? 'mdi-content-save-outline' : 'mdi-file-outline'
        "
        size="28"
      />
      <p>{{ emptyLabel }}</p>
    </div>
  </div>
</template>

<style scoped>
.r-asset-strip {
  width: 100%;
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

/* Wrap layout (Save data subtab) — a responsive grid instead of a single
   horizontal scroll row. Tiles fill their grid cell, so the per-tile
   flex-basis below is overridden. */
.r-asset-strip--wrap .r-asset-strip__track {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  overflow: visible;
  scroll-snap-type: none;
  padding: 4px 0;
}
.r-asset-strip--wrap .r-asset-strip__tile {
  flex: initial;
  scroll-snap-align: none;
}

.r-asset-strip__tile {
  appearance: none;
  border: 0;
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
  gap: 6px;
  text-align: left;
  cursor: pointer;
  border-radius: var(--r-radius-md);
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-asset-strip__tile:hover {
  transform: translateY(-2px);
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
}
.r-asset-strip__tile--static:hover .r-asset-strip__thumb {
  border-color: transparent;
}

.r-asset-strip__thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  border: 2px solid transparent;
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-asset-strip__tile:hover .r-asset-strip__thumb {
  border-color: var(--r-color-border-strong);
}
.r-asset-strip__tile--active .r-asset-strip__thumb {
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 6px 18px
    color-mix(in srgb, var(--r-color-brand-primary) 35%, transparent);
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

.r-asset-strip__check {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  background: var(--r-color-brand-primary);
  color: white;
  border-radius: 50%;
  box-shadow: 0 2px 6px color-mix(in srgb, black 35%, transparent);
}

.r-asset-strip__meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 0 2px;
  min-width: 0;
}

.r-asset-strip__name {
  margin: 0;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-strip__tile--active .r-asset-strip__name {
  color: var(--r-color-brand-primary);
}

.r-asset-strip__sub {
  margin: 0;
  font-size: 10px;
  color: var(--r-color-fg-muted);
  display: flex;
  gap: 4px;
  align-items: baseline;
}
.r-asset-strip__dot {
  opacity: 0.6;
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
  justify-content: flex-end;
  gap: 2px;
  padding: 0 2px;
}

.r-asset-strip__tip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 360px;
}
.r-asset-strip__tip-name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  word-break: break-all;
}
.r-asset-strip__tip-sub {
  font-size: 11px;
  opacity: 0.85;
}

.r-asset-strip__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 12px;
  color: var(--r-color-fg-muted);
  text-align: center;
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-asset-strip__empty p {
  margin: 0;
  font-size: 12px;
}

html[data-bp~="xs"] .r-asset-strip__tile {
  flex: 0 0 120px;
}
</style>
