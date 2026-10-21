<script setup lang="ts">
// BrandingRandomArtwork (romm-themeable): the Random entry's artwork, cycling through the
// usable packs so every step shows one real pack's tiles together.
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import {
  artworkUrl,
  type PreviewSlot,
  type ThemePack,
  type ThemeableClient,
} from "@/services/api/themeable";
import BrandingArtwork from "@/v2/components/Settings/BrandingArtwork.vue";
import { useArtworkCycle } from "@/v2/composables/useArtworkCycle";

const props = defineProps<{
  packs: ThemePack[];
  client: ThemeableClient;
}>();

const { t } = useI18n();

const ids = computed(() => props.packs.map((p) => p.id));

function preload(id: string): Promise<unknown> {
  const slots = Object.keys(props.client.preview) as PreviewSlot[];
  return Promise.all(
    slots.map((slot) => {
      const img = new Image();
      img.src = artworkUrl(props.client, id, slot);
      // A missing file shows RomM's own artwork, so a failed load still lets the switch happen.
      return img.decode().catch(() => undefined);
    }),
  );
}

const { current } = useArtworkCycle(ids, () => props.client.random_cycle_ms, {
  preload,
});
const currentName = computed(
  () => props.packs.find((p) => p.id === current.value)?.name ?? "",
);
</script>

<template>
  <span v-if="current" class="r-v2-branding-random">
    <span class="r-v2-branding-random__stack">
      <Transition name="r-v2-branding-random-fade">
        <BrandingArtwork
          :id="current"
          :key="current"
          class="r-v2-branding-random__layer"
          :client="client"
        />
      </Transition>
    </span>
    <span class="r-v2-branding-random__name">
      {{ t("branding.random-showing", { name: currentName }) }}
    </span>
  </span>
</template>

<style scoped>
.r-v2-branding-random {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
}

/* Both layers share one grid cell, so the outgoing and incoming packs cross-fade in place. */
.r-v2-branding-random__stack {
  display: grid;
}

.r-v2-branding-random__layer {
  grid-area: 1 / 1;
}

.r-v2-branding-random-fade-enter-active,
.r-v2-branding-random-fade-leave-active {
  transition: opacity var(--r-motion-slow) var(--r-motion-ease-in-out);
}

.r-v2-branding-random-fade-enter-from,
.r-v2-branding-random-fade-leave-to {
  opacity: 0;
}

.r-v2-branding-random__name {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
}
</style>
