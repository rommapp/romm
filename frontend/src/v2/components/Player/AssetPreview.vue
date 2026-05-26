<script setup lang="ts">
// Big "now showing" preview of the asset the user is about to resume
// from. Two distinct treatments:
//
// • State: a 16:9 stage dominated by the screenshot (or a placeholder
//   when the user never captured one). Metadata sits below the stage.
//
// • Save: a featured horizontal card with a large save icon and the
//   metadata laid out inline — saves never carry a screenshot, so the
//   stage area would be wasted space. Pair with <AssetList> below.
//
// Renders an empty state when nothing is selected — distinct from "no
// items available", which the chooser components own.
import { RIcon, RTag, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";

const props = defineProps<{
  asset: SaveSchema | StateSchema | null;
  type: AssetType;
}>();

defineEmits<{
  clear: [];
}>();

const { t, locale } = useI18n();

const screenshotUrl = computed(() => {
  if (!props.asset) return null;
  if ("screenshot" in props.asset && props.asset.screenshot?.download_path) {
    return props.asset.screenshot.download_path;
  }
  return null;
});

const heading = computed(() =>
  props.type === "save"
    ? t("play.resume-from-save")
    : t("play.resume-from-state"),
);

const emptyText = computed(() =>
  props.type === "save"
    ? t("play.no-save-selected")
    : t("play.no-state-selected"),
);
</script>

<template>
  <div class="r-asset-preview">
    <p class="r-asset-preview__eyebrow">{{ heading }}</p>

    <!-- ── State filled ────────────────────────────────────── -->
    <div
      v-if="asset && type === 'state'"
      class="r-asset-preview__filled r-asset-preview__filled--state"
    >
      <div class="r-asset-preview__stage">
        <div
          v-if="screenshotUrl"
          class="r-asset-preview__stage-img"
          :style="{ backgroundImage: `url(${screenshotUrl})` }"
        />
        <div v-else class="r-asset-preview__stage-placeholder">
          <RIcon icon="mdi-image-off-outline" size="64" />
          <p>{{ t("play.no-screenshot-available") }}</p>
        </div>
        <button
          type="button"
          class="r-asset-preview__clear"
          :aria-label="t('common.clear')"
          @click="$emit('clear')"
        >
          <RIcon icon="mdi-close" size="14" />
        </button>
      </div>

      <div class="r-asset-preview__meta">
        <p class="r-asset-preview__name">
          {{ asset.file_name }}
          <RTooltip activator="parent" location="top" :open-delay="400">
            <div class="r-asset-preview__tip">
              <span class="r-asset-preview__tip-name">
                {{ asset.file_name }}
              </span>
              <span class="r-asset-preview__tip-sub">
                {{ t("rom.updated") }}:
                {{ formatTimestamp(asset.updated_at, locale) }}
              </span>
            </div>
          </RTooltip>
        </p>
        <div class="r-asset-preview__chips">
          <span class="r-asset-preview__chip">
            <RIcon icon="mdi-clock-outline" size="12" />
            {{ formatRelativeDate(asset.updated_at) }}
          </span>
          <span class="r-asset-preview__chip">
            <RIcon icon="mdi-weight" size="12" />
            {{ formatBytes(asset.file_size_bytes) }}
          </span>
          <RTag
            v-if="asset.emulator"
            tone="warning"
            size="x-small"
            :text="asset.emulator"
          />
        </div>
        <p class="r-asset-preview__exact">
          <RIcon icon="mdi-calendar-clock" size="11" />
          {{ formatTimestamp(asset.updated_at, locale) }}
        </p>
      </div>
    </div>

    <!-- ── Save filled ─────────────────────────────────────── -->
    <div
      v-else-if="asset && type === 'save'"
      class="r-asset-preview__filled r-asset-preview__filled--save"
    >
      <div class="r-asset-preview__save-card">
        <div class="r-asset-preview__save-icon" aria-hidden="true">
          <RIcon icon="mdi-content-save" size="44" />
        </div>
        <div class="r-asset-preview__save-meta">
          <p class="r-asset-preview__name">
            {{ asset.file_name }}
            <RTooltip activator="parent" location="top" :open-delay="400">
              <div class="r-asset-preview__tip">
                <span class="r-asset-preview__tip-name">
                  {{ asset.file_name }}
                </span>
                <span class="r-asset-preview__tip-sub">
                  {{ t("rom.updated") }}:
                  {{ formatTimestamp(asset.updated_at, locale) }}
                </span>
              </div>
            </RTooltip>
          </p>
          <div class="r-asset-preview__chips">
            <span class="r-asset-preview__chip">
              <RIcon icon="mdi-clock-outline" size="12" />
              {{ formatRelativeDate(asset.updated_at) }}
            </span>
            <span class="r-asset-preview__chip">
              <RIcon icon="mdi-weight" size="12" />
              {{ formatBytes(asset.file_size_bytes) }}
            </span>
            <RTag
              v-if="asset.emulator"
              tone="warning"
              size="x-small"
              :text="asset.emulator"
            />
          </div>
          <p class="r-asset-preview__exact">
            <RIcon icon="mdi-calendar-clock" size="11" />
            {{ formatTimestamp(asset.updated_at, locale) }}
          </p>
        </div>
        <button
          type="button"
          class="r-asset-preview__clear r-asset-preview__clear--inline"
          :aria-label="t('common.clear')"
          @click="$emit('clear')"
        >
          <RIcon icon="mdi-close" size="14" />
        </button>
      </div>
    </div>

    <!-- ── Empty ───────────────────────────────────────────── -->
    <div v-else class="r-asset-preview__empty">
      <div class="r-asset-preview__empty-art">
        <RIcon
          :icon="
            type === 'save' ? 'mdi-content-save-outline' : 'mdi-image-area'
          "
          size="56"
        />
      </div>
      <p class="r-asset-preview__empty-title">{{ emptyText }}</p>
      <p class="r-asset-preview__empty-hint">
        {{ t("play.start-fresh-hint") }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.r-asset-preview {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-asset-preview__eyebrow {
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 10px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}

/* ── State filled ─────────────────────────────────────────── */

.r-asset-preview__filled {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-asset-preview__stage {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  border: 1px solid var(--r-color-border);
  box-shadow:
    0 12px 28px color-mix(in srgb, black 35%, transparent),
    0 0 0 1px color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
}
.r-asset-preview__stage-img {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
}
.r-asset-preview__stage-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  background: linear-gradient(
    135deg,
    var(--r-color-cover-placeholder),
    var(--r-color-cover-placeholder-bright)
  );
}
.r-asset-preview__stage-placeholder p {
  margin: 0;
  font-size: 12px;
}

.r-asset-preview__clear {
  position: absolute;
  top: 10px;
  right: 10px;
  appearance: none;
  border: 1px solid color-mix(in srgb, white 22%, transparent);
  background: color-mix(in srgb, black 55%, transparent);
  color: white;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  cursor: pointer;
  backdrop-filter: blur(6px);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-asset-preview__clear:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 65%,
    transparent
  );
}

/* The save card's clear button sits inside the card (no stage), so it
   uses the surface palette rather than the dark overlay variant. */
.r-asset-preview__clear--inline {
  position: static;
  border-color: var(--r-color-border);
  background: var(--r-color-surface);
  color: var(--r-color-fg-secondary);
  align-self: flex-start;
  flex-shrink: 0;
  backdrop-filter: none;
}
.r-asset-preview__clear--inline:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  color: var(--r-color-danger-fg);
}

/* ── Save filled (featured card) ──────────────────────────── */

.r-asset-preview__save-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border-radius: var(--r-radius-md);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, var(--r-color-surface)),
    var(--r-color-surface)
  );
  border: 1px solid var(--r-color-border);
  box-shadow: 0 8px 22px color-mix(in srgb, black 25%, transparent);
  min-height: 130px;
}

.r-asset-preview__save-icon {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  border-radius: var(--r-radius-md);
  background: color-mix(in srgb, var(--r-color-brand-primary) 20%, transparent);
  color: var(--r-color-brand-primary);
  flex-shrink: 0;
}

.r-asset-preview__save-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* ── Shared meta ──────────────────────────────────────────── */

.r-asset-preview__meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 2px;
}

.r-asset-preview__name {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-asset-preview__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.r-asset-preview__chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-pill);
  font-size: 11px;
  color: var(--r-color-fg-secondary);
}

.r-asset-preview__exact {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-asset-preview__tip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-width: 360px;
}
.r-asset-preview__tip-name {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  word-break: break-all;
}
.r-asset-preview__tip-sub {
  font-size: 11px;
  opacity: 0.85;
}

/* ── Empty state ──────────────────────────────────────────── */

.r-asset-preview__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 36px 20px;
  text-align: center;
  border: 1px dashed var(--r-color-border);
  border-radius: var(--r-radius-md);
  min-height: 220px;
}
.r-asset-preview__empty-art {
  display: grid;
  place-items: center;
  width: 84px;
  height: 84px;
  border-radius: 50%;
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
  margin-bottom: 4px;
}
.r-asset-preview__empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-asset-preview__empty-hint {
  margin: 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  max-width: 260px;
}
</style>
