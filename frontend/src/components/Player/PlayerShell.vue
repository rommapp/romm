<script setup lang="ts">
// PlayerShell renders the pre-game chrome a simple v2 player needs: cover column,
// settings card, play and back buttons, and the full-bleed running stage. A
// player supplies only the controls above the Play button and whatever it
// mounts as a stage, through the `settings` and `stage` slots. A player that
// needs its own on-stage chrome replaces the quit button via `stage-actions`.
import { useI18n } from "vue-i18n";
import GameCover from "@/components/shared/GameCover.vue";
import { usePlayFocus } from "@/composables/usePlayFocus";
import { usePlayerNav } from "@/composables/usePlayerNav";
import { useStageActive } from "@/composables/useStageActive";
import { RBtn, RCard, RSpinner } from "@/lib";
import type { DetailedRom, SimpleRom } from "@/stores/roms";

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
const { romRoute, platformRoute } = usePlayerNav(
  props.romId,
  () => props.heroRom?.platform_id,
);
useStageActive(() => props.running);
usePlayFocus(
  ".r-player__play",
  () => props.ready,
  () => props.running,
);
</script>

<template>
  <section v-if="heroRom" class="r-player">
    <div v-if="!running" class="r-player__config">
      <aside class="r-player__cover">
        <GameCover
          class="r-player__cover-box"
          :rom="heroRom"
          :title="title"
          :identified="heroRom?.is_identified ?? true"
          :morph-id="romId"
          style-context="player"
          morph-static
          hover-motion
        />
        <h1 class="r-player__title">
          {{ title }}
        </h1>
        <p class="r-player__subtitle">
          {{ platformLabel }}
        </p>
      </aside>

      <RCard class="r-player__panel" variant="flat">
        <div class="r-player__settings">
          <slot name="settings" />

          <RBtn
            size="large"
            variant="flat"
            color="primary"
            block
            prepend-icon="mdi-play-circle"
            class="r-player__play"
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
            :to="romRoute"
          >
            {{ t("play.back-to-game-details") }}
          </RBtn>
          <RBtn
            block
            variant="text"
            size="small"
            prepend-icon="mdi-view-grid-outline"
            :to="platformRoute"
            :disabled="!platformRoute"
          >
            {{ t("play.back-to-gallery") }}
          </RBtn>
        </div>
      </RCard>

      <div v-if="$slots.brand" class="r-player__brand">
        <slot name="brand" />
      </div>
    </div>

    <div v-else class="r-player__stage-wrap">
      <slot name="stage" />
      <slot v-if="$slots['stage-actions']" name="stage-actions" />
      <RBtn
        v-else
        class="r-player__quit"
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

  <section v-else class="r-player__loading">
    <RSpinner :size="40" :aria-label="t('common.loading')" />
  </section>
</template>

<style scoped>
.r-player {
  position: relative;
  min-height: calc(100vh - var(--r-nav-h));
  padding: 24px var(--r-row-pad) 48px;
}

.r-player__config {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 24px;
  max-width: 820px;
  margin: 0 auto;
}

.r-player__cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.r-player__cover-box {
  --r-cover-radius: var(--r-radius-lg);
}
/* 2D box art keeps a drop shadow; alt-art floats frame-free. */
.r-player__cover-box:not(.game-cover--alt) {
  box-shadow: 0 18px 36px color-mix(in srgb, black 55%, transparent);
}

.r-player__title {
  margin: 10px 0 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-bold);
  line-height: 1.2;
}

.r-player__subtitle {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-player__panel {
  background: var(--r-color-bg-elevated) !important;
  border: 1px solid var(--r-color-border) !important;
  border-radius: var(--r-radius-lg) !important;
  backdrop-filter: blur(18px);
  display: flex !important;
  flex-direction: column;
  overflow: hidden;
}

.r-player__settings {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.r-player__play {
  margin-top: 8px;
}

.r-player__brand {
  grid-column: 1 / -1;
  margin-top: 12px;
}

.r-player__stage-wrap {
  position: fixed;
  inset: var(--r-stage-inset);
  background: var(--r-color-canvas-bg);
  z-index: 1;
}
.r-player__quit {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
}

.r-player__loading {
  min-height: calc(100vh - var(--r-nav-h));
  display: grid;
  place-items: center;
}

html[data-bp~="xs"] .r-player__config {
  grid-template-columns: 1fr;
}
html[data-bp~="xs"] .r-player__cover {
  max-width: 240px;
  margin: 0 auto;
}
</style>
