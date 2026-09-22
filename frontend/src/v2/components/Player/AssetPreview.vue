<script setup lang="ts">
// Preview of the asset to resume from: a screenshot stage for states, one
// compact row for saves (thumbnail when the save has a screenshot; relabelled
// as the write target when a state is armed).
import { RIcon, RTag, RTooltip } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { formatBytes, formatRelativeDate, formatTimestamp } from "@/utils";
import AssetFavoriteMark from "@/v2/components/shared/AssetFavoriteMark.vue";
import AssetLabels from "@/v2/components/shared/AssetLabels.vue";
import { dateOf, type AssetDateField } from "@/v2/utils/assets";
import { toCssUrl } from "@/v2/utils/css";

defineOptions({ inheritAttrs: false });

export type AssetType = "save" | "state";

const props = withDefaults(
  defineProps<{
    asset: SaveSchema | StateSchema | null;
    type: AssetType;
    /** Set false where the surrounding panel already carries the title. */
    showHeading?: boolean;
    /** Set false where the picker has no empty selection to clear to. */
    clearable?: boolean;
    /** A state boots first, so a save is only where progress is written. */
    stateArmed?: boolean;
    /** Which timestamp to show. Set it to whatever the list this preview sits
     *  above is ordered by, so both read the same asset as newest. */
    timestamp?: AssetDateField;
  }>(),
  {
    showHeading: true,
    clearable: true,
    stateArmed: false,
    timestamp: "updated",
  },
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

const saveIsTarget = computed(() => props.type === "save" && props.stateArmed);

const heading = computed(() => {
  if (saveIsTarget.value) return t("play.save-progress-to");
  return props.type === "save"
    ? t("play.resume-from-save")
    : t("play.resume-from-state");
});

const timeLabel = computed(() =>
  props.timestamp === "created" ? t("rom.created") : t("rom.updated"),
);

const emptyText = computed(() =>
  props.type === "save"
    ? t("play.no-save-selected")
    : t("play.no-state-selected"),
);
</script>

<template>
  <div
    class="r-asset-preview"
    :class="{ 'r-asset-preview--save': type === 'save' }"
  >
    <p v-if="showHeading" class="r-asset-preview__eyebrow">{{ heading }}</p>

    <!-- ── Stage (states only) ────────────────────────────────── -->
    <div
      v-if="type === 'state'"
      class="r-asset-preview__stage"
      :class="{ 'r-asset-preview__stage--empty': !asset }"
    >
      <!-- Screenshot or placeholder. -->
      <template v-if="asset">
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

      <!-- Empty: friendly art. -->
      <div v-else class="r-asset-preview__stage-fill">
        <div class="r-asset-preview__empty-art">
          <RIcon icon="mdi-image-area" size="24" />
        </div>
        <p class="r-asset-preview__empty-title">{{ emptyText }}</p>
        <p class="r-asset-preview__empty-hint">
          {{ t("play.start-fresh-hint") }}
        </p>
      </div>

      <AssetFavoriteMark
        v-if="asset"
        class="r-asset-preview__stage-fav"
        :class="{ 'r-asset-preview__stage-fav--clearable': clearable }"
        :favorite="asset.is_favorite"
        :size="16"
      />

      <!-- Clear button — only when something is selected. -->
      <button
        v-if="asset && clearable"
        type="button"
        class="r-asset-preview__clear"
        :aria-label="t('common.clear')"
        @click="$emit('clear')"
      >
        <RIcon icon="mdi-close" size="14" />
      </button>
    </div>

    <!-- ── Body: meta strip, plus badge and clear for saves ────── -->
    <div
      class="r-asset-preview__body"
      :class="{ 'r-asset-preview__body--empty': !asset }"
    >
      <div
        v-if="type === 'save'"
        class="r-asset-preview__save-badge"
        :class="{ 'r-asset-preview__save-badge--shot': screenshotUrl }"
        :style="
          screenshotUrl
            ? { backgroundImage: toCssUrl(screenshotUrl) }
            : undefined
        "
      >
        <RIcon
          v-if="!screenshotUrl"
          :icon="asset ? 'mdi-content-save' : 'mdi-content-save-outline'"
          size="22"
        />
      </div>

      <div v-if="asset" class="r-asset-preview__meta">
        <p class="r-asset-preview__title">
          <span class="r-asset-preview__name">{{ asset.file_name }}</span>
          <AssetFavoriteMark
            v-if="type === 'save'"
            :favorite="asset.is_favorite"
            :size="14"
          />
          <RTooltip activator="parent" location="top" :open-delay="400">
            <div class="r-asset-preview__tip">
              <span class="r-asset-preview__tip-name">
                {{ asset.file_name }}
              </span>
              <span class="r-asset-preview__tip-sub">
                {{ timeLabel }}:
                {{ formatTimestamp(dateOf(asset, timestamp), locale) }}
              </span>
            </div>
          </RTooltip>
        </p>
        <AssetLabels class="r-asset-preview__labels" :asset="asset" />
        <div class="r-asset-preview__chips">
          <RTag
            v-if="'slot' in asset && asset.slot"
            tone="brand"
            size="x-small"
            prepend-icon="mdi-content-save-all-outline"
            :text="asset.slot"
          />
          <RTag
            v-if="type === 'state' && asset.emulator"
            tone="warning"
            size="x-small"
            :text="asset.emulator"
          />
          <span class="r-asset-preview__chip">
            <RIcon icon="mdi-weight" size="12" />
            {{ formatBytes(asset.file_size_bytes) }}
          </span>
        </div>
        <p class="r-asset-preview__when">
          <RIcon icon="mdi-clock-outline" size="11" />
          {{ formatRelativeDate(dateOf(asset, timestamp)) }}
          <span class="r-asset-preview__when-exact">
            {{ formatTimestamp(dateOf(asset, timestamp), locale) }}
          </span>
        </p>
      </div>

      <!-- For states this stays as an empty block: the stage already carries
           the empty copy, and the reserved height keeps the strip below put. -->
      <div v-else class="r-asset-preview__meta r-asset-preview__meta--empty">
        <template v-if="type === 'save'">
          <p class="r-asset-preview__empty-title">{{ emptyText }}</p>
          <p v-if="!saveIsTarget" class="r-asset-preview__empty-hint">
            {{ t("play.start-fresh-hint") }}
          </p>
        </template>
      </div>

      <button
        v-if="asset && type === 'save' && clearable"
        type="button"
        class="r-asset-preview__clear r-asset-preview__clear--inline"
        :aria-label="t('common.clear')"
        @click="$emit('clear')"
      >
        <RIcon icon="mdi-close" size="14" />
      </button>
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
  gap: 8px;
  align-items: center;
  justify-content: center;
  color: var(--r-color-fg-muted);
  padding: 12px;
  text-align: center;
}
.r-asset-preview__stage-fill p {
  margin: 0;
  font-size: 12px;
}

/* State placeholder backdrop (no screenshot) inherits the cover-
   placeholder gradient on the base stage; just dim the foreground. */
.r-asset-preview__stage:not(.r-asset-preview__stage--empty)
  .r-asset-preview__stage-fill {
  background: linear-gradient(
    135deg,
    var(--r-color-cover-placeholder),
    var(--r-color-cover-placeholder-bright)
  );
}

/* ── Save row: badge + meta + clear, no stage ────────────── */
.r-asset-preview--save .r-asset-preview__body {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, var(--r-color-surface)),
    var(--r-color-surface)
  );
}
.r-asset-preview--save .r-asset-preview__body--empty {
  border-style: dashed;
  background: var(--r-color-surface);
}
.r-asset-preview__save-badge {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent);
  color: var(--r-color-brand-primary);
}
.r-asset-preview__save-badge--shot {
  width: 71px;
  border-radius: var(--r-radius-sm);
  background-size: cover;
  background-position: center;
}
.r-asset-preview__body--empty .r-asset-preview__save-badge {
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-muted);
}

/* Empty-state art — small circular badge with the type's icon. */
.r-asset-preview__empty-art {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-muted);
}
.r-asset-preview__stage-fill .r-asset-preview__empty-title {
  margin-bottom: -6px;
}
.r-asset-preview__empty-title {
  margin: 0;
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
/* 44px hit area around the 28px pill. */
.r-asset-preview__clear::before {
  content: "";
  position: absolute;
  inset: -8px;
}
.r-asset-preview__clear:hover {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 65%,
    transparent
  );
}

/* Off the screenshot the overlay-style clear button reads too heavy
   against a light surface; switch to a tonal pill. */
.r-asset-preview__clear--inline {
  position: relative;
  /* The stage variant is absolutely placed; in flow those offsets would push
     the button off the centre the layout already gives it. */
  top: auto;
  right: auto;
  flex-shrink: 0;
  border-color: var(--r-color-border);
  background: var(--r-color-bg-elevated);
  color: var(--r-color-fg-secondary);
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

/* ── Meta (shared shell) ──────────────────────────────────── */

.r-asset-preview__meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 2px;
  flex: 1;
  min-width: 0;
  /* Reserve the row even when content is shorter, so the strip below
     doesn't shift between filled and empty. */
  min-height: 70px;
}
.r-asset-preview__meta--empty {
  display: flex;
  align-items: center;
}
.r-asset-preview--save .r-asset-preview__meta--empty {
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 2px;
}

.r-asset-preview__title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.r-asset-preview__name {
  min-width: 0;
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
  align-items: center;
  gap: 6px;
}

.r-asset-preview__labels {
  row-gap: 6px;
}

.r-asset-preview__stage-fav {
  position: absolute;
  top: 12px;
  right: 12px;
  filter: drop-shadow(0 1px 4px color-mix(in srgb, black 75%, transparent));
}
.r-asset-preview__stage-fav--clearable {
  right: 46px;
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

.r-asset-preview__when {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--r-color-fg-secondary);
  font-variant-numeric: tabular-nums;
}
.r-asset-preview__when-exact {
  color: var(--r-color-fg-muted);
}
/* Separates the exact stamp from the relative one it trails. */
.r-asset-preview__when-exact::before {
  content: "·";
  margin-right: 4px;
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

/* Phones read the save preview like a save row: thumbnail and name together,
   then labels, facts and the timestamp each across the full width. */
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__body {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas:
    "badge title clear"
    "labels labels labels"
    "facts facts facts"
    "when when when";
  align-items: center;
  column-gap: 10px;
  row-gap: 6px;
  min-height: 70px;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__save-badge {
  grid-area: badge;
  align-self: start;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__meta {
  display: contents;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__meta--empty {
  display: flex;
  grid-area: title;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__title {
  grid-area: title;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__clear--inline {
  grid-area: clear;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__labels {
  grid-area: labels;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__chips {
  grid-area: facts;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__when {
  grid-area: when;
}
html[data-bp~="xs"] .r-asset-preview--save .r-asset-preview__name {
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
