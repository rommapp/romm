<script setup lang="ts">
// BrandingArtwork (romm-themeable): one pack's artwork as visitors would see it.
import { useI18n } from "vue-i18n";
import {
  artworkUrl,
  type PreviewSlot,
  type ThemeableClient,
} from "@/services/api/themeable";

const props = defineProps<{
  id: string;
  client: ThemeableClient;
}>();

const { t } = useI18n();

function url(slot: PreviewSlot): string {
  return artworkUrl(props.client, props.id, slot);
}
</script>

<template>
  <span class="r-v2-branding-art" aria-hidden="true">
    <span
      class="r-v2-branding-art__tile r-v2-branding-art__tile--background"
      :title="t('branding.art-background')"
    >
      <img :src="url('background')" alt="" loading="lazy" />
      <img
        class="r-v2-branding-art__logo"
        :src="url('logo')"
        alt=""
        loading="lazy"
      />
    </span>
    <span
      class="r-v2-branding-art__tile r-v2-branding-art__tile--wordmark r-v2-branding-art__tile--dark"
      :title="t('branding.art-wordmark-dark')"
    >
      <img :src="url('wordmark')" alt="" loading="lazy" />
    </span>
    <span
      class="r-v2-branding-art__tile r-v2-branding-art__tile--wordmark r-v2-branding-art__tile--light"
      :title="t('branding.art-wordmark-light')"
    >
      <img :src="url('wordmark')" alt="" loading="lazy" />
    </span>
    <span
      class="r-v2-branding-art__tile r-v2-branding-art__tile--favicon"
      :title="t('branding.art-favicon')"
    >
      <img :src="url('favicon')" alt="" width="24" height="24" loading="lazy" />
    </span>
  </span>
</template>

<style scoped>
.r-v2-branding-art {
  display: flex;
  flex-wrap: wrap;
  gap: var(--r-space-2);
}

.r-v2-branding-art__tile {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  overflow: hidden;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}

.r-v2-branding-art__tile--background {
  width: 120px;
}

.r-v2-branding-art__tile--background > img:first-child {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.r-v2-branding-art__logo {
  position: relative;
  width: 32px;
  height: 32px;
  object-fit: contain;
}

.r-v2-branding-art__tile--wordmark {
  width: 104px;
  padding: 0 var(--r-space-2);
}

.r-v2-branding-art__tile--wordmark img {
  max-width: 100%;
  height: 20px;
  object-fit: contain;
}

/* The wordmark sits on the page background in both modes, so show it on both. */
.r-v2-branding-art__tile--dark {
  background: var(--r-color-canvas-bg);
}

.r-v2-branding-art__tile--light {
  background: var(--r-color-overlay-emphasis-bg);
}

.r-v2-branding-art__tile--favicon {
  width: 48px;
  background: var(--r-color-surface);
}

html[data-bp~="xs"] .r-v2-branding-art__tile {
  height: 40px;
}

html[data-bp~="xs"] .r-v2-branding-art__tile--background {
  width: 96px;
}

html[data-bp~="xs"] .r-v2-branding-art__logo {
  width: 26px;
  height: 26px;
}

html[data-bp~="xs"] .r-v2-branding-art__tile--wordmark {
  width: 80px;
}

html[data-bp~="xs"] .r-v2-branding-art__tile--wordmark img {
  height: 16px;
}

html[data-bp~="xs"] .r-v2-branding-art__tile--favicon {
  width: 40px;
}
</style>
