<script setup lang="ts">
// CoverColumn — fixed-width left column with the ROM cover (or a placeholder
// if none resolves). Sized via --r-cover-w and top-aligned so tall right-
// column content doesn't stretch the image.
//
// `romId` opts the cover into the shared-element morph from GameCard via
// `view-transition-name: rom-cover-{id}`. Source side (GameCard) tags the
// matching element imperatively at click time — see useViewTransition.
import { computed } from "vue";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  src: string | null | undefined;
  alt: string;
  romId?: number | string;
}>();

const morphStyle = computed(() =>
  props.romId != null
    ? { viewTransitionName: `rom-cover-${props.romId}` }
    : undefined,
);
</script>

<template>
  <div class="r-v2-det-cover">
    <img v-if="src" :src="src" :alt="alt" :style="morphStyle" />
    <div v-else class="r-v2-det-cover__placeholder" :style="morphStyle">
      {{ alt }}
    </div>
  </div>
</template>

<style scoped>
.r-v2-det-cover {
  flex-shrink: 0;
  align-self: flex-start;
  /* No sticky needed: GameDetails fits the main viewport exactly and
     only the inner tab panel scrolls. Cover sits at its natural Y and
     stays there because nothing scrolls in its context. */
  padding-top: 40px;
  width: var(--r-cover-w);
}

.r-v2-det-cover img {
  width: 100%;
  border-radius: var(--r-radius-lg);
  display: block;
}

.r-v2-det-cover__placeholder {
  width: var(--r-cover-w);
  height: 320px;
  border-radius: var(--r-radius-lg);
  background: var(--r-color-cover-placeholder);
  display: grid;
  place-items: center;
  text-align: center;
  padding: 24px;
  color: var(--r-color-fg-faint);
  font-size: 13px;
}

html[data-bp~="xs"] .r-v2-det-cover {
  width: 100px;
  margin-top: 0;
}
html[data-bp~="xs"] .r-v2-det-cover__placeholder {
  width: 100px;
  height: 134px;
}
</style>
