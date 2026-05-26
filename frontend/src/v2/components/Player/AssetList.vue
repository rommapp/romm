<script setup lang="ts">
// Vertical list for saves — paired with <AssetStrip> (horizontal tile
// strip for states) below the AssetPreview in the EmulatorJS view.
//
// Saves never carry a screenshot, so the tile-strip's 16:9 area would
// be wasted space. This list variant trades the visual thumbnail for
// information density: each row shows the filename in full, both the
// relative time AND the exact timestamp, plus the size and emulator
// chip. The selected row gets a brand-color left rail + bg tint.
import { RIcon, RTag, RTooltip } from "@v2/lib";
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
</script>

<template>
  <div class="r-asset-list">
    <ul v-if="assets.length > 0" class="r-asset-list__items">
      <li
        v-for="asset in assets"
        :key="asset.id"
        class="r-asset-list__item"
        :class="{
          'r-asset-list__item--active': asset.id === selectedId,
        }"
      >
        <button
          type="button"
          class="r-asset-list__row"
          :aria-pressed="asset.id === selectedId"
          @click="$emit('select', asset)"
        >
          <span class="r-asset-list__icon" aria-hidden="true">
            <RIcon
              :icon="type === 'save' ? 'mdi-content-save' : 'mdi-file-outline'"
              size="22"
            />
          </span>

          <span class="r-asset-list__main">
            <span class="r-asset-list__name">{{ asset.file_name }}</span>
            <span class="r-asset-list__chips">
              <RTag
                v-if="asset.emulator"
                tone="warning"
                size="x-small"
                :text="asset.emulator"
              />
              <span class="r-asset-list__chip">
                <RIcon icon="mdi-weight" size="11" />
                {{ formatBytes(asset.file_size_bytes) }}
              </span>
            </span>
          </span>

          <span class="r-asset-list__time">
            <span class="r-asset-list__relative">
              {{ formatRelativeDate(asset.updated_at) }}
            </span>
            <span class="r-asset-list__exact">
              {{ formatTimestamp(asset.updated_at, locale) }}
            </span>
          </span>

          <span class="r-asset-list__check" aria-hidden="true">
            <RIcon
              v-if="asset.id === selectedId"
              icon="mdi-check-circle"
              size="18"
            />
          </span>

          <RTooltip activator="parent" location="top" :open-delay="400">
            <div class="r-asset-list__tip">
              <span class="r-asset-list__tip-name">{{ asset.file_name }}</span>
              <span class="r-asset-list__tip-sub">
                {{ t("rom.updated") }}:
                {{ formatTimestamp(asset.updated_at, locale) }}
              </span>
            </div>
          </RTooltip>
        </button>
      </li>
    </ul>

    <div v-else class="r-asset-list__empty">
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
.r-asset-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.r-asset-list__items {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  min-height: 0;
  max-height: 300px;
  scrollbar-color: var(--r-color-border-strong) transparent;
  scrollbar-width: thin;
}
.r-asset-list__items::-webkit-scrollbar {
  width: 6px;
}
.r-asset-list__items::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 6px;
}

.r-asset-list__item {
  position: relative;
}

.r-asset-list__row {
  appearance: none;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-bg-elevated);
  width: 100%;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--r-radius-md);
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: var(--r-color-fg);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    background var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
  position: relative;
  overflow: hidden;
}
.r-asset-list__row:hover {
  border-color: var(--r-color-border-strong);
  background: var(--r-color-surface);
  transform: translateY(-1px);
}
.r-asset-list__item--active .r-asset-list__row {
  border-color: var(--r-color-brand-primary);
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}
.r-asset-list__item--active .r-asset-list__row::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--r-color-brand-primary);
}

.r-asset-list__icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  flex-shrink: 0;
}
.r-asset-list__item--active .r-asset-list__icon {
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  color: var(--r-color-brand-primary);
}

.r-asset-list__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-asset-list__name {
  display: block;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-asset-list__item--active .r-asset-list__name {
  color: var(--r-color-brand-primary);
}
.r-asset-list__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.r-asset-list__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 10px;
  color: var(--r-color-fg-secondary);
}

.r-asset-list__time {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}
.r-asset-list__relative {
  font-size: 11px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-asset-list__exact {
  font-size: 10px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-asset-list__check {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  color: var(--r-color-fg-faint);
}
.r-asset-list__item--active .r-asset-list__check {
  color: var(--r-color-brand-primary);
}

.r-asset-list__empty {
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
.r-asset-list__empty p {
  margin: 0;
  font-size: 12px;
}

.r-asset-list__tip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 360px;
}
.r-asset-list__tip-name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  word-break: break-all;
}
.r-asset-list__tip-sub {
  font-size: 11px;
  opacity: 0.85;
}

/* Tighten the row on small screens so the time column doesn't push
   the filename off-screen. The exact timestamp is the first to go —
   the tooltip still has it. */
html[data-bp~="xs"] .r-asset-list__exact {
  display: none;
}
html[data-bp~="xs"] .r-asset-list__row {
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  padding: 8px 10px;
}
</style>
