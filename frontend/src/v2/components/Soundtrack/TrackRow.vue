<script setup lang="ts">
// One row of the soundtrack track list.
//
// Split out of Panel so the list can be virtualised: only visible rows mount,
// which keeps the per-row RMenu (and its document-level listener) proportional
// to the viewport rather than to the size of the library.
import { RBtn, RDivider, RMenu, RMenuItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import useMusicFavorites from "@/stores/musicFavorites";
import { formatBytes } from "@/utils";
import type { PanelTrack } from "@/v2/utils/soundtrackTracks";

const props = defineProps<{
  track: PanelTrack;
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

function fmt(s: number | undefined | null) {
  if (s == null || !Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60)
    .toString()
    .padStart(2, "0");
  return `${m}:${sec}`;
}
</script>

<template>
  <div
    :data-track-id="track.id"
    class="r-v2-stp__row"
    :class="{
      'r-v2-stp__row--active': active,
      'r-v2-stp__row--playing': playing,
      'r-v2-stp__row--buffering': buffering,
    }"
  >
    <button
      type="button"
      class="r-v2-stp__row-btn"
      :aria-label="t('rom.play-track', { title: track.title })"
      @click="emit('select', track.id)"
    >
      <!-- No per-track thumb: playback state is conveyed entirely by the
           row's border + a subtle pulsing glow when the track is actually
           playing (vs. just selected/paused). -->
      <div class="r-v2-stp__row-meta">
        <div class="r-v2-stp__row-title">{{ track.title }}</div>
        <div v-if="track.subtitle" class="r-v2-stp__row-subtitle">
          {{ track.subtitle }}
        </div>
      </div>
    </button>

    <div class="r-v2-stp__row-right">
      <span v-if="track.durationSeconds" class="r-v2-stp__row-duration">
        {{ fmt(track.durationSeconds) }}
      </span>
      <span v-if="track.fileSizeBytes != null" class="r-v2-stp__row-size">
        {{ formatBytes(track.fileSizeBytes) }}
      </span>
      <RMenu location="bottom end" :offset="6" width="200px">
        <template #activator="{ props: activatorProps }">
          <RBtn
            v-bind="activatorProps"
            icon="mdi-dots-vertical"
            variant="text"
            size="small"
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
}

.r-v2-stp__row {
  flex: 0 0 auto;
  display: flex;
  align-items: stretch;
  gap: var(--r-space-2);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface);
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-stp__row:hover {
  border-color: var(--r-color-brand-primary-hover);
}
.r-v2-stp__row--active {
  border-color: var(--r-color-brand-primary);
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent),
    var(--r-color-surface)
  );
}
.r-v2-stp__row--playing,
.r-v2-stp__row--buffering {
  /* Anchor for the orbit pseudo. */
  position: relative;
}
.r-v2-stp__row--playing::before,
.r-v2-stp__row--buffering::before {
  content: "";
  position: absolute;
  /* The pseudo covers the row plus a 1px overshoot on every side so
     the visible ring lands right on the row's border. Padding sets
     the ring thickness; the mask-composite trick below clips the
     conic gradient down to that ring. Thicker ring (3px) gives the
     arcs more weight on the perimeter. */
  inset: -1px;
  padding: 3px;
  border-radius: inherit;
  /* Two bright arcs sitting 180° apart so the row reads as having
     two pulses chasing each other. Each arc spans ~40% of the
     circumference with a long, smooth tail-in / tail-out at six
     intermediate opacities — that breaks up the visible staircase
     conic gradients normally show at a small number of stops. The
     conic gradient's `from` angle is the animated custom property
     so only the arc pattern travels; the pseudo's box stays put. */
  background: conic-gradient(
    from var(--r-stp-orbit-angle),
    /* Arc A — peak at 12.5%, ~40% wide with a long diffuse tail. */
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 0%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 4%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 8%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 11%,
    var(--r-color-brand-primary) 12.5%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 14%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 17%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 21%,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 25%,
    transparent 32%,
    /* Empty quadrant — clear separation between the two pulses. */ transparent
      50%,
    /* Arc B — same envelope, 180° away from arc A. */
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 50%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 54%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 58%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 61%,
    var(--r-color-brand-primary) 62.5%,
    color-mix(in srgb, var(--r-color-brand-primary) 75%, transparent) 64%,
    color-mix(in srgb, var(--r-color-brand-primary) 45%, transparent) 67%,
    color-mix(in srgb, var(--r-color-brand-primary) 22%, transparent) 71%,
    color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent) 75%,
    transparent 82%,
    transparent 100%
  );
  /* "Gradient border" mask: paint the conic gradient only on the
     padding ring. The two solid masks (one clipped to `content-box`,
     the other to the full box) are XORed — what's left is the ring
     between them. */
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  mask-composite: exclude;
  /* Sub-pixel blur softens any residual conic-gradient banding that
     the gradient stops alone can't fully erase. */
  filter: blur(0.4px);
  pointer-events: none;
  animation: r-v2-stp-row-spin 3.2s linear infinite;
}
.r-v2-stp__row--buffering::before {
  animation-duration: 1.2s;
}
.r-v2-stp__row-btn {
  appearance: none;
  border: 0;
  background: transparent;
  padding: var(--r-space-2) var(--r-space-3);
  flex: 1;
  display: flex;
  align-items: center;
  cursor: pointer;
  color: var(--r-color-fg);
  min-width: 0;
  text-align: left;
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
  gap: var(--r-space-2);
  padding: 0 var(--r-space-2);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  font-variant-numeric: tabular-nums;
}
.r-v2-stp__row-duration {
  min-width: 44px;
  text-align: right;
}
@keyframes r-v2-stp-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
@keyframes r-v2-stp-row-spin {
  /* Top edge — right half, from start point (45°) to the right corner.
     Velocity gradually drops as we approach the corner. */
  0% {
    --r-stp-orbit-angle: 0deg;
  }
  2.5% {
    --r-stp-orbit-angle: 22.7deg;
  }
  5% {
    --r-stp-orbit-angle: 30.5deg;
  }
  7.5% {
    --r-stp-orbit-angle: 34.3deg;
  }
  10% {
    --r-stp-orbit-angle: 36.6deg;
  }
  12.5% {
    --r-stp-orbit-angle: 38deg;
  }
  15% {
    --r-stp-orbit-angle: 39.1deg;
  }
  17.5% {
    --r-stp-orbit-angle: 39.8deg;
  }
  20% {
    --r-stp-orbit-angle: 40.4deg;
  }
  /* Right corner area — velocity gradually picks up. Extra samples
     here so the transition into the side doesn't read as a jump. */
  22.5% {
    --r-stp-orbit-angle: 41.5deg;
  }
  23.5% {
    --r-stp-orbit-angle: 43.5deg;
  }
  24.25% {
    --r-stp-orbit-angle: 46deg;
  }
  25% {
    --r-stp-orbit-angle: 49.3deg;
  }
  /* Bottom edge — slow at first, then sprinting through the centre. */
  27.5% {
    --r-stp-orbit-angle: 49.8deg;
  }
  30% {
    --r-stp-orbit-angle: 50.5deg;
  }
  32.5% {
    --r-stp-orbit-angle: 51.3deg;
  }
  35% {
    --r-stp-orbit-angle: 52.5deg;
  }
  37.5% {
    --r-stp-orbit-angle: 54.2deg;
  }
  40% {
    --r-stp-orbit-angle: 56.9deg;
  }
  42.5% {
    --r-stp-orbit-angle: 61.8deg;
  }
  45% {
    --r-stp-orbit-angle: 73.2deg;
  }
  47% {
    --r-stp-orbit-angle: 100deg;
  }
  48.3% {
    --r-stp-orbit-angle: 135deg;
  }
  49.5% {
    --r-stp-orbit-angle: 170deg;
  }
  51.7% {
    --r-stp-orbit-angle: 198.4deg;
  }
  55% {
    --r-stp-orbit-angle: 210.5deg;
  }
  57.5% {
    --r-stp-orbit-angle: 214.3deg;
  }
  60% {
    --r-stp-orbit-angle: 216.6deg;
  }
  62.5% {
    --r-stp-orbit-angle: 218.1deg;
  }
  65% {
    --r-stp-orbit-angle: 219.1deg;
  }
  67.5% {
    --r-stp-orbit-angle: 219.8deg;
  }
  70% {
    --r-stp-orbit-angle: 220.4deg;
  }
  /* Left corner area — symmetric with the right corner. */
  72.5% {
    --r-stp-orbit-angle: 221.5deg;
  }
  73.5% {
    --r-stp-orbit-angle: 223.5deg;
  }
  74.25% {
    --r-stp-orbit-angle: 226deg;
  }
  75% {
    --r-stp-orbit-angle: 229.3deg;
  }
  /* Top edge, left half coming back to the start position. */
  77.5% {
    --r-stp-orbit-angle: 229.8deg;
  }
  80% {
    --r-stp-orbit-angle: 230.5deg;
  }
  82.5% {
    --r-stp-orbit-angle: 231.3deg;
  }
  85% {
    --r-stp-orbit-angle: 232.5deg;
  }
  87.5% {
    --r-stp-orbit-angle: 234.2deg;
  }
  90% {
    --r-stp-orbit-angle: 236.9deg;
  }
  92.5% {
    --r-stp-orbit-angle: 241.8deg;
  }
  95% {
    --r-stp-orbit-angle: 253.2deg;
  }
  97% {
    --r-stp-orbit-angle: 280deg;
  }
  98.3% {
    --r-stp-orbit-angle: 315deg;
  }
  99.5% {
    --r-stp-orbit-angle: 350deg;
  }
  100% {
    --r-stp-orbit-angle: 360deg;
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-stp__row--playing::before,
  .r-v2-stp__row--buffering::before {
    animation: none;
    /* Drop the moving arc for a soft static halo so playing is still
       distinguishable from paused without motion. */
    background: none;
    box-shadow: 0 0 0 3px
      color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent);
  }
}
</style>
