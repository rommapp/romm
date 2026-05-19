<script setup lang="ts">
// GameHeader — right-column header for the details view.
// Four rows, top to bottom:
//   1. Title
//   2. Meta (year · platform-icon + platform · verified RTag)
//   3. Tags (regions + languages + custom tags) — RTag primitive
//   4. GameActions (Play · Download · Favorite · Share · More)
//
// Metadata-provider links live in the Metadata tab, not the header.
// Genre/franchise belong in the Overview tab info grid.
import { RPlatformIcon, RTag } from "@v2/lib";
import type { DetailedRom } from "@/stores/roms";
import GameActions from "@/v2/components/GameActions/GameActions.vue";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: DetailedRom;
  title: string;
  platformLabel: string;
  releaseDate: string | null;
  verified: boolean;
  regions: string[];
  languages: string[];
  tags: string[];
  canPlay: boolean;
}>();

const actions = useGameActions(() => props.rom);
</script>

<template>
  <div class="r-v2-det-header">
    <h1 class="r-v2-det-header__title">
      {{ title }}
    </h1>

    <div class="r-v2-det-header__meta">
      <span v-if="releaseDate">{{ releaseDate }}</span>
      <span v-if="releaseDate && platformLabel" class="r-v2-det-header__sep">
        ·
      </span>
      <router-link
        v-if="actions.platformPath.value"
        :to="actions.platformPath.value"
        class="r-v2-det-header__platform"
        :aria-label="`Browse ${platformLabel}`"
      >
        <RPlatformIcon
          :slug="rom.platform_slug"
          :fs-slug="rom.platform_fs_slug"
          :alt="platformLabel"
          :size="16"
        />
        {{ platformLabel }}
      </router-link>
      <span
        v-if="(releaseDate || platformLabel) && verified"
        class="r-v2-det-header__sep"
      >
        ·
      </span>
      <RTag
        v-if="verified"
        icon="mdi-check-decagram"
        text="Verified"
        tone="success"
        size="small"
      />
    </div>

    <div
      v-if="regions.length || languages.length || tags.length"
      class="r-v2-det-header__tags"
    >
      <RTag
        v-for="r in regions"
        :key="`r-${r}`"
        :text="r"
        tone="info"
        size="small"
      />
      <RTag
        v-for="l in languages"
        :key="`l-${l}`"
        :text="l"
        tone="brand"
        size="small"
      />
      <RTag v-for="t in tags" :key="`t-${t}`" :text="t" size="small" />
    </div>

    <GameActions :rom="rom" :can-play="canPlay" />
  </div>
</template>

<style scoped>
.r-v2-det-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 24px;
}

.r-v2-det-header__title {
  font-size: var(--r-font-size-4xl);
  font-weight: var(--r-font-weight-extrabold);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 2px 0;
  text-shadow: 0 2px 20px color-mix(in srgb, black 50%, transparent);
}

.r-v2-det-header__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13.5px;
  color: var(--r-color-fg-secondary);
}
.r-v2-det-header__sep {
  opacity: 0.3;
}
.r-v2-det-header__platform {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: inherit;
  text-decoration: none;
  cursor: pointer;
  border-radius: var(--r-radius-sm);
  transition: color 0.12s ease;
}
.r-v2-det-header__platform:hover {
  color: var(--r-color-fg);
}

.r-v2-det-header__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

html[data-bp~="xs"] .r-v2-det-header__title {
  font-size: 20px;
}
</style>
