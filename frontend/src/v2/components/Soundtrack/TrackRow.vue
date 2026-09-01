<script setup lang="ts">
// One row of the (virtualised) track list: only visible rows mount, keeping
// the per-row RMenu count proportional to the viewport, not the library.
import { RBtn, RDivider, RIcon, RMenu, RMenuItem, RSpinner } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import useMusicFavorites from "@/stores/musicFavorites";
import { formatBytes } from "@/utils";
import type { PanelTrack } from "@/v2/utils/soundtrackTracks";
import { formatTrackTime } from "@/v2/utils/time";

const props = defineProps<{
  track: PanelTrack;
  /** Zero-based position in the displayed queue. */
  index: number;
  active?: boolean;
  playing?: boolean;
  buffering?: boolean;
  deletable?: boolean;
  favoritable?: boolean;
}>();
const emit = defineEmits<{
  (e: "select", fileId: number): void;
  (e: "download", track: PanelTrack): void;
  (e: "delete", track: PanelTrack): void;
  (e: "toggle-favorite", track: PanelTrack): void;
}>();

const { t } = useI18n();
const favorites = useMusicFavorites();

const isFavorite = computed(() => favorites.isFavorite(props.track.id));
const isPending = computed(() => favorites.isPending(props.track.id));
</script>

<template>
  <div
    :data-track-id="track.id"
    class="r-v2-stp__row"
    :class="{
      'r-v2-stp__row--active': active,
      'r-v2-stp__row--playing': playing,
    }"
  >
    <button
      type="button"
      class="r-v2-stp__row-btn"
      :aria-label="t('rom.play-track', { title: track.title })"
      @click="emit('select', track.id)"
    >
      <span class="r-v2-stp__row-lead" aria-hidden="true">
        <RSpinner v-if="buffering" :size="14" :width="2" />
        <template v-else>
          <span class="r-v2-stp__row-index">{{ index + 1 }}</span>
          <span class="r-v2-stp__row-eq"><i /><i /><i /></span>
          <RIcon
            class="r-v2-stp__row-glyph"
            :icon="active && playing ? 'mdi-pause' : 'mdi-play'"
            size="18"
          />
        </template>
      </span>
      <span class="r-v2-stp__row-meta">
        <span class="r-v2-stp__row-title">{{ track.title }}</span>
        <span v-if="track.subtitle" class="r-v2-stp__row-subtitle">
          {{ track.subtitle }}
        </span>
      </span>
    </button>

    <div class="r-v2-stp__row-right">
      <span v-if="track.durationSeconds" class="r-v2-stp__row-duration">
        {{ formatTrackTime(track.durationSeconds) }}
      </span>
      <span v-if="track.fileSizeBytes != null" class="r-v2-stp__row-size">
        {{ formatBytes(track.fileSizeBytes) }}
      </span>
      <RBtn
        v-if="favoritable"
        class="r-v2-stp__row-fav"
        :class="{ 'r-v2-stp__row-fav--on': isFavorite }"
        :icon="isFavorite ? 'mdi-heart' : 'mdi-heart-outline'"
        variant="text"
        size="x-small"
        :loading="isPending"
        :tooltip="
          t(isFavorite ? 'rom.remove-from-favorites' : 'rom.add-to-favorites')
        "
        :aria-label="
          t(isFavorite ? 'rom.remove-from-favorites' : 'rom.add-to-favorites')
        "
        :aria-pressed="isFavorite"
        @click="emit('toggle-favorite', track)"
      />
      <RMenu location="bottom end" :offset="6" width="200px">
        <template #activator="{ props: activatorProps }">
          <RBtn
            v-bind="activatorProps"
            icon="mdi-dots-vertical"
            variant="text"
            size="x-small"
            :tooltip="t('rom.more-actions')"
            :aria-label="t('rom.more-actions')"
          />
        </template>
        <RMenuItem
          icon="mdi-play"
          :label="t('rom.play')"
          @click="emit('select', track.id)"
        />
        <RDivider />
        <RMenuItem
          v-if="favoritable"
          :icon="isFavorite ? 'mdi-heart' : 'mdi-heart-outline'"
          :label="
            t(isFavorite ? 'rom.remove-from-favorites' : 'rom.add-to-favorites')
          "
          :disabled="isPending"
          @click="emit('toggle-favorite', track)"
        />
        <RMenuItem
          icon="mdi-download-outline"
          :label="t('common.download')"
          @click="emit('download', track)"
        />
        <RMenuItem
          v-if="deletable"
          icon="mdi-delete-outline"
          :label="t('common.delete')"
          variant="danger"
          @click="emit('delete', track)"
        />
      </RMenu>
    </div>
  </div>
</template>

<style scoped>
/* Fixed height: RVirtualScroller positions rows from `getItemHeight`, so the
   rendered row must match ROW_HEIGHT in Panel.vue (48px + 4px gap). */
.r-v2-stp__row {
  height: 48px;
  margin-bottom: 4px;
  box-sizing: border-box;
  display: flex;
  align-items: stretch;
  gap: var(--r-space-2);
  border-radius: var(--r-radius-md);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

html[data-input="mouse"] .r-v2-stp__row:hover,
html[data-input="touch"] .r-v2-stp__row:hover {
  background: var(--r-color-surface-hover);
}

.r-v2-stp__row--active {
  background: color-mix(in srgb, var(--r-color-brand-primary) 12%, transparent);
}

html[data-input="mouse"] .r-v2-stp__row--active:hover,
html[data-input="touch"] .r-v2-stp__row--active:hover {
  background: color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
}

.r-v2-stp__row-btn {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0 var(--r-space-2);
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  cursor: pointer;
  color: var(--r-color-fg);
  min-width: 0;
  text-align: left;
  border-radius: inherit;
}

/* Leading cell: queue position / play glyph / equalizer / spinner. */
.r-v2-stp__row-lead {
  flex: 0 0 34px;
  display: grid;
  place-items: center;
}

/* The three states stack in the same grid cell; visibility picks one. */
.r-v2-stp__row-lead > * {
  grid-area: 1 / 1;
}

.r-v2-stp__row-index {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-v2-stp__row-glyph {
  visibility: hidden;
  color: var(--r-color-fg);
}

.r-v2-stp__row--active .r-v2-stp__row-glyph {
  color: var(--r-color-brand-primary);
}

/* Equalizer: three bars that dance while the track plays and freeze
   mid-height when it is paused. */
.r-v2-stp__row-eq {
  visibility: hidden;
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 14px;
}

.r-v2-stp__row-eq i {
  width: 3px;
  height: 100%;
  border-radius: 1px;
  background: var(--r-color-brand-primary);
  transform: scaleY(0.4);
  transform-origin: bottom;
}

.r-v2-stp__row--active .r-v2-stp__row-index {
  visibility: hidden;
}

.r-v2-stp__row--active .r-v2-stp__row-eq {
  visibility: visible;
}

.r-v2-stp__row--playing .r-v2-stp__row-eq i {
  animation: r-v2-stp-eq 1s ease-in-out infinite;
}

.r-v2-stp__row--playing .r-v2-stp__row-eq i:nth-child(2) {
  animation-delay: -0.66s;
}

.r-v2-stp__row--playing .r-v2-stp__row-eq i:nth-child(3) {
  animation-delay: -0.33s;
}

@keyframes r-v2-stp-eq {
  0%,
  100% {
    transform: scaleY(0.3);
  }
  50% {
    transform: scaleY(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__row--playing .r-v2-stp__row-eq i {
    animation: none;
    transform: scaleY(0.7);
  }
}

/* Pointer or keyboard on the row swaps the lead cell for a play / pause
   glyph. Hover is gated to pointer modalities (constitution: no bare
   :hover competing with pad focus). */
html[data-input="mouse"] .r-v2-stp__row:hover .r-v2-stp__row-index,
html[data-input="mouse"] .r-v2-stp__row:hover .r-v2-stp__row-eq,
.r-v2-stp__row-btn:focus-visible .r-v2-stp__row-index,
.r-v2-stp__row-btn:focus-visible .r-v2-stp__row-eq {
  visibility: hidden;
}

html[data-input="mouse"] .r-v2-stp__row:hover .r-v2-stp__row-glyph,
.r-v2-stp__row-btn:focus-visible .r-v2-stp__row-glyph {
  visibility: visible;
}

.r-v2-stp__row-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-stp__row-title {
  font-weight: var(--r-font-weight-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-stp__row--active .r-v2-stp__row-title {
  color: var(--r-color-brand-primary);
}

.r-v2-stp__row-subtitle {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-stp__row-right {
  display: flex;
  align-items: center;
  gap: var(--r-space-1);
  padding: 0 var(--r-space-2);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}

.r-v2-stp__row-duration {
  min-width: 44px;
  text-align: right;
}

.r-v2-stp__row-size {
  min-width: 56px;
  text-align: right;
}

/* The heart stays put once favorited; otherwise it only surfaces on
   pointer hover or focus. Non-mouse modalities keep it always visible
   since they have no hover to reveal it with. */
html[data-input="mouse"]
  .r-v2-stp__row:not(:hover):not(:focus-within)
  .r-v2-stp__row-fav:not(.r-v2-stp__row-fav--on) {
  opacity: 0;
}

.r-v2-stp__row-fav {
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-stp__row-fav--on {
  color: var(--r-color-fav);
}
</style>
