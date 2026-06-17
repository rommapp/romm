<script setup lang="ts">
// Horizontal strip of save/state tiles — the "carousel" below the
// selected-asset preview in the EmulatorJS pre-game view.
//
// State tiles show their 16:9 screenshot prominently; saves fall back
// to a large save icon. The currently-selected tile gets a brand-color
// ring + check badge so it reads as "you're about to resume from this
// one". Hovering lifts the tile; tiles are focusable for gamepad/key
// navigation.
//
// Overflowing items scroll horizontally with snap; the strip never
// wraps. On narrower screens the tiles shrink in width.
import { RIcon, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";
type Asset = SaveSchema | StateSchema;

const props = defineProps<{
  assets: Asset[];
  type: AssetType;
  selectedId: number | null;
}>();

defineEmits<{
  select: [asset: Asset];
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
</script>

<template>
  <div class="r-asset-strip">
    <div v-if="assets.length > 0" class="r-asset-strip__track">
      <button
        v-for="asset in assets"
        :key="asset.id"
        type="button"
        class="r-asset-strip__tile"
        :class="{
          'r-asset-strip__tile--active': asset.id === selectedId,
        }"
        :aria-pressed="asset.id === selectedId"
        @click="$emit('select', asset)"
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
            v-if="asset.id === selectedId"
            class="r-asset-strip__check"
            aria-hidden="true"
          >
            <RIcon icon="mdi-check" size="14" />
          </span>
        </div>
        <div class="r-asset-strip__meta">
          <p class="r-asset-strip__name">{{ asset.file_name }}</p>
          <p class="r-asset-strip__sub">
            <span>{{ formatRelativeDate(asset.updated_at) }}</span>
            <span class="r-asset-strip__dot" aria-hidden="true">·</span>
            <span>{{ formatBytes(asset.file_size_bytes) }}</span>
          </p>
        </div>
        <RTooltip activator="parent" location="top" :open-delay="400">
          <div class="r-asset-strip__tip">
            <span class="r-asset-strip__tip-name">{{ asset.file_name }}</span>
            <span class="r-asset-strip__tip-sub">
              {{ t("rom.updated") }}:
              {{ formatTimestamp(asset.updated_at, locale) }}
            </span>
          </div>
        </RTooltip>
      </button>
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
