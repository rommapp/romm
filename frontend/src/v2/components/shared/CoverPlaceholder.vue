<script setup lang="ts">
// CoverPlaceholder — shown in place of a cover when a rom has no image.
// Paints the per-name procedural artwork (RomM's "missing" / "unmatched"
// art) and overlays the title on top with a scrim + text-shadow so it
// stays legible over the coloured art. Fills its (positioned) parent, so
// it drops straight into a sized art box (GameCard, CoverColumn).
import { computed } from "vue";
import { coverPlaceholderArt } from "@/v2/utils/covers";

interface Props {
  /** Seed for the per-name colour hash + which icon shows. */
  name: string;
  /** Title painted over the art. */
  title: string;
  /** Identified rom (grid icon) vs unmatched (question mark). */
  identified?: boolean;
}
const props = withDefaults(defineProps<Props>(), { identified: true });

const artUrl = computed(() =>
  coverPlaceholderArt(props.name, props.identified),
);
</script>

<template>
  <div class="cover-ph">
    <img class="cover-ph__art" :src="artUrl" alt="" aria-hidden="true" />
    <span class="cover-ph__title">{{ title }}</span>
  </div>
</template>

<style scoped>
.cover-ph {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.cover-ph__art {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
/* Centre-weighted scrim so the title reads over the busy art without
   washing out the whole illustration. */
.cover-ph::after {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, black 50%, transparent),
    color-mix(in srgb, black 12%, transparent) 78%
  );
}
.cover-ph__title {
  position: relative;
  z-index: 1;
  max-width: 100%;
  padding: 8px 10px;
  text-align: center;
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.35;
  color: var(--r-color-overlay-fg);
  text-shadow: 0 1px 5px color-mix(in srgb, black 80%, transparent);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
