<script setup lang="ts">
// PlayerShell — the pre-game chrome a simple v2 player needs: cover column,
// settings card, play and back buttons, and the full-bleed running stage. A
// player supplies only the controls above the Play button and whatever it
// mounts as a stage, through the `settings` and `stage` slots.
import { RBtn, RCard, RSpinner } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { DetailedRom, SimpleRom } from "@/stores/roms";
import GameCover from "@/v2/components/shared/GameCover.vue";
import { usePlayerNav } from "@/v2/composables/usePlayerNav";

interface Props {
  /** Full rom once loaded, else the cover-only seed during the morph-in. */
  heroRom: DetailedRom | SimpleRom | null;
  title: string;
  platformLabel: string;
  /** Route rom id, so the morph tag matches even while the hero is a seed. */
  romId: number;
  ready: boolean;
  running: boolean;
  quitting?: boolean;
}

const props = withDefaults(defineProps<Props>(), { quitting: false });

const emit = defineEmits<{
  play: [];
  quit: [];
}>();

const { t } = useI18n();
const { backToRom, backToPlatform } = usePlayerNav(
  props.romId,
  () => props.heroRom?.platform_id,
);
</script>

<template>
  <section v-if="heroRom" class="r-v2-player">
    <div v-if="!running" class="r-v2-player__config">
      <aside class="r-v2-player__cover">
        <GameCover
          class="r-v2-player__cover-box"
          :rom="heroRom"
          :title="title"
          :identified="heroRom?.is_identified ?? true"
          :morph-id="romId"
          style-context="player"
          morph-static
          hover-motion
        />
        <h1 class="r-v2-player__title">
          {{ title }}
        </h1>
        <p class="r-v2-player__subtitle">
          {{ platformLabel }}
        </p>
      </aside>

      <RCard class="r-v2-player__panel" variant="flat">
        <div class="r-v2-player__settings">
          <slot name="settings" />

          <RBtn
            size="large"
            variant="flat"
            color="primary"
            block
            prepend-icon="mdi-play-circle"
            class="r-v2-player__play"
            :loading="!ready"
            :disabled="!ready"
            @click="emit('play')"
          >
            {{ t("play.play") }}
          </RBtn>

          <RBtn
            block
            variant="text"
            size="small"
            prepend-icon="mdi-arrow-left"
            @click="backToRom"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
          <RBtn
            block
            variant="text"
            size="small"
            prepend-icon="mdi-view-grid-outline"
            @click="backToPlatform"
          >
            {{ t("play.back-to-gallery") }}
          </RBtn>
        </div>
      </RCard>

      <div v-if="$slots.brand" class="r-v2-player__brand">
        <slot name="brand" />
      </div>
    </div>

    <div v-else class="r-v2-player__stage-wrap">
      <slot name="stage" />
      <RBtn
        class="r-v2-player__quit"
        variant="translucent"
        prepend-icon="mdi-exit-to-app"
        :loading="quitting"
        :disabled="quitting"
        @click="emit('quit')"
      >
        {{ t("play.quit") }}
      </RBtn>
    </div>
  </section>

  <section v-else class="r-v2-player__loading">
    <RSpinner :size="40" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-v2-player {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 48px;
}

.r-v2-player__config {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.r-v2-player__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.r-v2-player__cover-box {
  --r-cover-radius: var(--r-radius-lg);
}
/* 2D box art keeps a drop shadow; alt-art floats frame-free. */
.r-v2-player__cover-box:not(.game-cover--alt) {
  box-shadow: 0 18px 36px color-mix(in srgb, black 55%, transparent);
}

.r-v2-player__title {
  margin: 10px 0 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}

.r-v2-player__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-player__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-v2-player__settings {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-v2-player__play {
  margin-top: 8px;
}

.r-v2-player__brand {
  grid-column: 1 / -1;
  margin-top: 12px;
}

.r-v2-player__stage-wrap {
  position: fixed;
  inset: var(--r-nav-h) 0 0 0;
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-v2-player__quit {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
}

.r-v2-player__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-v2-player__config {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-v2-player__cover {
  max-width: 240px;
  margin: 0 auto;
}
</style>
