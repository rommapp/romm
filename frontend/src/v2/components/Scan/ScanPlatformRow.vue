<script setup lang="ts">
// ScanPlatformRow — single ROM row inside a ScanPlatform body.
//
// Extracted so the same row markup can be rendered both inside a plain
// <ul> (small platforms) and inside an RVirtualScroller slot (large
// platforms, hundreds+ of ROMs streaming in during an initial scan).
// Provider chip logic and cover-fallback selection live here.
import { RImg, RTag } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import type { SimpleRom } from "@/stores/roms";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import {
  getMissingCoverImage,
  getUnmatchedCoverImage,
} from "@/v2/utils/covers";
import { activeProviders } from "@/v2/utils/metadataProviders";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
}>();

const { t } = useI18n();
const { toWebp } = useWebpSupport();

// Title shown for the row: the identified ROM name once metadata resolves,
// otherwise the raw filename while it's still being identified.
const displayName = computed(() => props.rom.name || props.rom.fs_name);

// Plays a one-shot reveal animation when THIS row's ROM flips from
// "identifying" to "identified" in place (filename → real name). Guarded
// against the virtual scroller recycling the instance onto a different ROM
// (id change), so the animation only ever fires on a genuine identification
// event — never while scrolling.
const revealing = ref(false);
// The cover pop is driven by the image's own `load` instead of the
// identification flip: the real artwork downloads a beat after the metadata
// lands, so popping on the flip would animate the placeholder and the real
// cover would then slip in flat. Popping on load makes the artwork itself
// spring in.
const coverPop = ref(false);
watch(
  () => props.rom,
  (next, prev) => {
    if (!prev || next.id !== prev.id) {
      revealing.value = false;
      coverPop.value = false;
      return;
    }
    if (next.is_identified && !prev.is_identified && next.name) {
      revealing.value = true;
    }
  },
);

function onCoverLoad() {
  // Only the resolved real artwork pops — not the procedural placeholder
  // shown while a ROM is still unidentified.
  if (props.rom.is_identified && props.rom.path_cover_small) {
    coverPop.value = true;
  }
}

function coverFor(rom: SimpleRom): string {
  if (rom.path_cover_small) return toWebp(rom.path_cover_small);
  // Fallback procedural cover — distinct artwork for identified vs.
  // unmatched ROMs so a glance at the row tells you whether scanning
  // matched anything.
  return rom.is_identified
    ? getMissingCoverImage(rom.name || rom.fs_name)
    : getUnmatchedCoverImage(rom.name || rom.fs_name);
}
</script>

<template>
  <router-link
    :to="{ name: ROUTES.ROM, params: { rom: props.rom.id } }"
    class="r-v2-scan-platform__rom"
  >
    <RImg
      :src="coverFor(props.rom)"
      :alt="displayName"
      :width="36"
      :height="48"
      cover
      class="r-v2-scan-platform__cover"
      :class="{ 'r-v2-scan-platform__cover--reveal': coverPop }"
      @load="onCoverLoad"
    />
    <div class="r-v2-scan-platform__rom-text">
      <div
        class="r-v2-scan-platform__rom-name"
        :class="{ 'r-v2-scan-platform__rom-name--reveal': revealing }"
      >
        {{ displayName }}
      </div>
      <div class="r-v2-scan-platform__rom-file">
        {{ props.rom.fs_name }}
      </div>
    </div>
    <div class="r-v2-scan-platform__rom-meta">
      <template v-if="props.rom.is_identifying">
        <RTag
          tone="warning"
          size="x-small"
          prepend-icon="mdi-magnify"
          :text="t('scan.identifying', 'Identifying…')"
          class="r-v2-scan-platform__identifying"
        />
      </template>
      <template v-else>
        <RTag
          v-if="props.rom.is_unidentified"
          tone="danger"
          size="x-small"
          prepend-icon="mdi-close"
          :text="t('scan.not-identified')"
          class="r-v2-scan-platform__badge-pop"
        />
        <span
          v-for="(provider, i) in activeProviders(props.rom)"
          :key="provider.key"
          class="r-v2-scan-platform__provider"
          :title="provider.title"
          :style="{
            ...(provider.bg ? { background: provider.bg } : {}),
            animationDelay: `${i * 70}ms`,
          }"
        >
          <img
            :src="`/assets/scrappers/${provider.logo}`"
            :alt="provider.title"
            width="16"
            height="16"
          />
        </span>
      </template>
    </div>
  </router-link>
</template>

<style scoped>
.r-v2-scan-platform__rom {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-top: 1px solid var(--r-color-border);
  /* Fixed row height — required for RVirtualScroller's offset table to
     match what the row actually renders at. Padding + 48px cover +
     border = 65px. */
  box-sizing: border-box;
  height: 65px;
  /* The row is a router-link to the ROM detail page. Strip the default
     link chrome so it reads as a regular row, and give it a hover tint
     to signal it's a click target. */
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
  /* Each freshly-scanned row slides in from the left as it streams into
     the log instead of popping in abruptly. `both` keeps it hidden until
     the first frame. (Stable id keys on the scroller ensure only the new
     row mounts, so this plays once per row — not on every insert.) */
  animation: scan-row-in 440ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
@keyframes scan-row-in {
  0% {
    opacity: 0;
    transform: translateX(-26px);
  }
  60% {
    opacity: 1;
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}
.r-v2-scan-platform__rom:hover,
.r-v2-scan-platform__rom:focus-visible {
  background: var(--r-color-surface-hover);
  outline: none;
}
.r-v2-scan-platform__cover {
  flex-shrink: 0;
  border-radius: var(--r-radius-sm);
  overflow: hidden;
}
/* When identification lands, the procedural placeholder swaps for the
   real artwork — flip it in with a springy pop so the match registers. */
.r-v2-scan-platform__cover--reveal {
  animation: scan-cover-in 560ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
@keyframes scan-cover-in {
  0% {
    transform: scale(0.5) rotate(-10deg);
    opacity: 0.35;
  }
  60% {
    transform: scale(1.08) rotate(3deg);
    opacity: 1;
  }
  100% {
    transform: scale(1) rotate(0);
  }
}
.r-v2-scan-platform__rom-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.r-v2-scan-platform__rom-name {
  font-size: 14px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Reveal animation when the title resolves from filename to identified
   ROM name: the new name slides up out of a soft blur while a brief brand
   glow sweeps over it, signalling a successful match at a glance. */
.r-v2-scan-platform__rom-name--reveal {
  animation:
    scan-name-reveal 460ms cubic-bezier(0.2, 0.8, 0.2, 1),
    scan-name-glow 900ms ease-out;
}

@keyframes scan-name-reveal {
  0% {
    opacity: 0;
    transform: translateY(7px) scale(0.98);
    filter: blur(4px);
  }
  55% {
    opacity: 1;
    filter: blur(0);
  }
  100% {
    transform: translateY(0) scale(1);
  }
}

@keyframes scan-name-glow {
  0% {
    color: var(--r-color-brand-primary);
    text-shadow: 0 0 14px
      color-mix(in srgb, var(--r-color-brand-primary) 55%, transparent);
  }
  100% {
    color: var(--r-color-fg);
    text-shadow: 0 0 0 transparent;
  }
}

.r-v2-scan-platform__rom-file {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  font-family: var(--r-font-family-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-scan-platform__rom-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.r-v2-scan-platform__provider {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: var(--r-color-surface);
  flex-shrink: 0;
  /* Provider chips spring in (staggered via inline animation-delay) the
     moment a match resolves — same overshoot curve as the cover pop. */
  animation: scan-badge-pop 420ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
/* The "not identified" pill shares the same entrance so a failed match
   lands with the same weight as a successful one. */
.r-v2-scan-platform__badge-pop {
  animation: scan-badge-pop 420ms cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
@keyframes scan-badge-pop {
  0% {
    opacity: 0;
    transform: scale(0.2) translateY(6px);
  }
  70% {
    transform: scale(1.12) translateY(0);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

/* While a ROM is still being identified, the pill gently breathes and its
   magnifier wobbles like it's actively searching. */
.r-v2-scan-platform__identifying {
  animation: scan-breathe 1.6s ease-in-out infinite;
}
.r-v2-scan-platform__identifying :deep(.r-tag__icon) {
  transform-origin: 60% 60%;
  animation: scan-magnify 1.3s ease-in-out infinite;
}
@keyframes scan-breathe {
  0%,
  100% {
    opacity: 0.82;
  }
  50% {
    opacity: 1;
  }
}
@keyframes scan-magnify {
  0%,
  100% {
    transform: rotate(-14deg) scale(1);
  }
  50% {
    transform: rotate(14deg) scale(1.18);
  }
}
.r-v2-scan-platform__provider img {
  display: block;
  object-fit: contain;
}

/* Honour reduced-motion: keep the information, drop all the juice. */
@media (prefers-reduced-motion: reduce) {
  .r-v2-scan-platform__rom,
  .r-v2-scan-platform__rom-name--reveal,
  .r-v2-scan-platform__cover--reveal,
  .r-v2-scan-platform__provider,
  .r-v2-scan-platform__badge-pop,
  .r-v2-scan-platform__identifying,
  .r-v2-scan-platform__identifying :deep(.r-tag__icon) {
    animation: none;
  }
}
</style>
