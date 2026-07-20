<script setup lang="ts">
// Big "now showing" preview of the asset the user is about to resume
// from. All three variants (state filled, save filled, empty) share a
// single skeleton — a 16:9 "stage" on top and a metadata strip below.
// Keeping the dimensions fixed prevents the AssetStrip/AssetList from
// jumping when the user switches tabs or clears the selection.
//
// What changes inside the stage:
//   • State: screenshot (or placeholder when none was captured).
//   • Save: a featured save graphic — saves never carry a screenshot,
//     so we lean on the icon + decorative backdrop.
//   • Empty: the empty-state art for the active type.
//
// The metadata strip carries the filename + chips + exact timestamp
// when something is selected, or the start-fresh hint when empty.
import { RIcon, RTag, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";
import { toCssUrl } from "@/v2/utils/css";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";

const props = withDefaults(
  defineProps<{
    asset: SaveSchema | StateSchema | null;
    type: AssetType;
    /** Set false where the surrounding panel already carries the title. */
    showHeading?: boolean;
  }>(),
  { showHeading: true },
);

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
    <p v-if="showHeading" class="r-asset-preview__eyebrow">{{ heading }}</p>

    <!-- ── Stage — same 16:9 dimensions across all variants ───── -->
    <div
      class="r-asset-preview__stage"
      :class="{
        'r-asset-preview__stage--save': type === 'save' && asset,
        'r-asset-preview__stage--empty': !asset,
      }"
    >
      <!-- State: screenshot or placeholder. -->
      <template v-if="asset && type === 'state'">
        <div v-if="screenshotUrl" class="r-asset-preview__stage-shot">
          <!-- Blurred cover copy fills the letterbox left by the
               contained frame, so the whole screenshot stays visible
               without dead bars on a stage wider than the frame. -->
          <div
            class="r-asset-preview__stage-backdrop"
            :style="{ backgroundImage: toCssUrl(screenshotUrl) }"
          />
          <div
            class="r-asset-preview__stage-img"
            :style="{ backgroundImage: toCssUrl(screenshotUrl) }"
          />
        </div>
        <div v-else class="r-asset-preview__stage-fill">
          <RIcon icon="mdi-image-off-outline" size="64" />
          <p>{{ t("play.no-screenshot-available") }}</p>
        </div>
      </template>

      <!-- Save: big icon + decorative backdrop. -->
      <div
        v-else-if="asset && type === 'save'"
        class="r-asset-preview__stage-fill"
      >
        <div class="r-asset-preview__save-medallion">
          <RIcon icon="mdi-content-save" size="56" />
        </div>
      </div>

      <!-- Empty: friendly art for the active type. -->
      <div v-else class="r-asset-preview__stage-fill">
        <div class="r-asset-preview__empty-art">
          <RIcon
            :icon="
              type === 'save' ? 'mdi-content-save-outline' : 'mdi-image-area'
            "
            size="40"
          />
        </div>
        <p class="r-asset-preview__empty-title">{{ emptyText }}</p>
      </div>

      <!-- Clear button — only when something is selected. -->
      <button
        v-if="asset"
        type="button"
        class="r-asset-preview__clear"
        :aria-label="t('common.clear')"
        @click="$emit('clear')"
      >
        <RIcon icon="mdi-close" size="14" />
      </button>
    </div>

    <!-- ── Meta — filled when selected, hint when empty ──────── -->
    <div v-if="asset" class="r-asset-preview__meta">
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
        <RTag
          v-if="'slot' in asset && asset.slot"
          tone="brand"
          size="x-small"
          prepend-icon="mdi-bookmark-outline"
          :label="t('play.slot')"
          :text="asset.slot"
        />
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

    <div v-else class="r-asset-preview__meta r-asset-preview__meta--empty">
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

/* ── Stage (shared shell) ─────────────────────────────────── */

.r-asset-preview__stage {
  position: relative;
  width: 100%;
  /* Flatter than 16:9 — the preview is a teaser, not a feature, and
     a shorter stage leaves the AssetList/AssetStrip below more room. */
  aspect-ratio: 5 / 2;
  border-radius: var(--r-radius-md);
  overflow: hidden;
  background: var(--r-color-cover-placeholder);
  border: 1px solid var(--r-color-border);
  box-shadow:
    0 12px 28px color-mix(in srgb, black 35%, transparent),
    0 0 0 1px color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
}

/* Save and empty variants use the surface backdrop instead of the
   cover-placeholder gradient — they're "panels" not screenshots. */
.r-asset-preview__stage--save,
.r-asset-preview__stage--empty {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, var(--r-color-surface)),
    var(--r-color-surface)
  );
  box-shadow: 0 8px 22px color-mix(in srgb, black 25%, transparent);
}

.r-asset-preview__stage--empty {
  border-style: dashed;
  background: var(--r-color-surface);
  box-shadow: none;
}

.r-asset-preview__stage-shot {
  position: absolute;
  inset: 0;
}

/* Blurred, dimmed cover copy behind the framed screenshot, turning the
   letterbox area into an intentional backdrop instead of empty bars. */
.r-asset-preview__stage-backdrop {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(18px) brightness(0.55) saturate(1.1);
  /* Overscan so the blur doesn't reveal soft edges at the frame border. */
  transform: scale(1.15);
}

/* The actual frame: contained so nothing is cropped top or bottom. */
.r-asset-preview__stage-img {
  position: absolute;
  inset: 0;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}

.r-asset-preview__stage-fill {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  padding: 16px;
  text-align: center;
}
.r-asset-preview__stage-fill p {
  margin: 0;
  font-size: 12px;
}

/* State placeholder backdrop (no screenshot) inherits the cover-
   placeholder gradient on the base stage; just dim the foreground. */
.r-asset-preview__stage:not(.r-asset-preview__stage--save):not(
    .r-asset-preview__stage--empty
  )
  .r-asset-preview__stage-fill {
  background: linear-gradient(
    135deg,
    var(--r-color-cover-placeholder),
    var(--r-color-cover-placeholder-bright)
  );
}

/* Save medallion — brand-tinted circle behind the save icon. Sized
   to feel like a badge inside the shorter stage, not a hero element. */
.r-asset-preview__save-medallion {
  display: grid;
  place-items: center;
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  color: var(--r-color-brand-primary);
}

/* Empty-state art — small circular badge with the type's icon. */
.r-asset-preview__empty-art {
  display: grid;
  place-items: center;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-muted);
}
.r-asset-preview__empty-title {
  font-size: 13px !important;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
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

/* On save / empty stages the overlay-style clear button reads too
   heavy against a light surface; switch to a tonal pill. */
.r-asset-preview__stage--save .r-asset-preview__clear,
.r-asset-preview__stage--empty .r-asset-preview__clear {
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-secondary);
  backdrop-filter: none;
}
.r-asset-preview__stage--save .r-asset-preview__clear:hover,
.r-asset-preview__stage--empty .r-asset-preview__clear:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 18%,
    transparent
  );
  color: var(--r-color-danger-fg);
}

/* ── Meta (shared shell) ──────────────────────────────────── */

.r-asset-preview__meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 2px;
  /* Reserve the row even when content is shorter, so the strip below
     doesn't shift between filled and empty. Worst case so far is
     name + wrapped chips + exact = ~3 lines @ ~22px each. */
  min-height: 70px;
}
.r-asset-preview__meta--empty {
  display: flex;
  align-items: center;
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

.r-asset-preview__empty-hint {
  margin: 0;
  font-size: 12px;
  color: var(--r-color-fg-muted);
  max-width: 360px;
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
</style>
