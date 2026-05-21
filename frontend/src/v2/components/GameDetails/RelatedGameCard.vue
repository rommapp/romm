<script setup lang="ts">
// RelatedGameCard — single card in the related-games strip.
// On mount, looks up the game in the local RomM library by IGDB id
// (`getRomByMetadataProvider`); when the lookup hits, the card links
// internally to the RomM detail page and renders an "In library"
// affordance (brand-tinted border + check overlay). When it misses,
// the card falls back to the IGDB game page so the user can still
// reach metadata for games they don't own.
//
// Mirrors v1's per-card pattern (frontend/src/components/common/Game/
// Card/Related.vue) — each card owns its own lookup so the parent
// grid stays a thin renderer.
import { RIcon, RTooltip } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import type { IGDBRelatedGame } from "@/__generated__";
import romApi from "@/services/api/rom";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ game: IGDBRelatedGame }>();

const romId = ref<number | null>(null);
const inLibrary = computed(() => romId.value !== null);

onMounted(async () => {
  try {
    const res = await romApi.getRomByMetadataProvider({
      field: "igdb_id",
      id: props.game.id,
    });
    romId.value = res.data.id;
  } catch {
    // Stay on the IGDB external fallback — game isn't in the
    // local library or the endpoint denied the lookup.
  }
});

const tag = computed(() => (inLibrary.value ? RouterLink : "a"));
const linkProps = computed(() =>
  inLibrary.value
    ? { to: `/rom/${romId.value}` }
    : {
        href: `https://www.igdb.com/games/${props.game.slug}`,
        target: "_blank",
        rel: "noopener noreferrer",
      },
);
</script>

<template>
  <RTooltip :text="game.name" location="top" :open-delay="400">
    <template #activator="{ props: activatorProps }">
      <component
        :is="tag"
        v-bind="{ ...activatorProps, ...linkProps }"
        class="related-card"
        :class="{ 'related-card--in-library': inLibrary }"
      >
        <div class="related-card__cover-wrap">
          <img
            v-if="game.cover_url"
            class="related-card__cover"
            :src="game.cover_url"
            :alt="game.name"
            loading="eager"
          />
          <div v-else class="related-card__cover related-card__cover--empty" />

          <!-- Category tag (DLC / Remake / Expansion …). IGDB ships
               this on every related game; surfaces what kind of
               relationship the entry represents. -->
          <span v-if="game.type" class="related-card__type">
            {{ game.type }}
          </span>

          <!-- In-library badge — only shows after the lookup resolves
               to a local ROM. Bottom-right corner so it never collides
               with the type tag (top-left). -->
          <span v-if="inLibrary" class="related-card__owned">
            <RIcon icon="mdi-check" size="11" />
          </span>
        </div>
        <div class="related-card__name">{{ game.name }}</div>
      </component>
    </template>
  </RTooltip>
</template>

<style scoped>
.related-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-decoration: none;
  color: inherit;
}

.related-card__cover-wrap {
  position: relative;
  border-radius: var(--r-radius-art);
  overflow: hidden;
  box-shadow: var(--r-elev-1);
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.related-card:hover .related-card__cover-wrap {
  transform: translateY(-2px);
  box-shadow: var(--r-elev-2);
}

.related-card--in-library .related-card__cover-wrap {
  /* Outline + soft glow signals ownership without crowding the card
     with extra text — the check overlay confirms it on hover/scan. */
  outline: 2px solid var(--r-color-brand-primary);
  outline-offset: -2px;
  box-shadow:
    var(--r-elev-1),
    0 0 0 0 var(--r-color-brand-primary),
    0 4px 18px color-mix(in srgb, var(--r-color-brand-primary) 25%, transparent);
}

.related-card__cover {
  aspect-ratio: 2 / 3;
  width: 100%;
  height: auto;
  object-fit: cover;
  display: block;
}
.related-card__cover--empty {
  aspect-ratio: 2 / 3;
  background: var(--r-color-bg-elevated);
}

.related-card__type {
  position: absolute;
  top: 6px;
  left: 6px;
  padding: 2px 7px;
  font-size: 9.5px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--r-color-overlay-fg);
  background: var(--r-color-overlay-scrim-strong);
  border-radius: var(--r-radius-chip);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.related-card__owned {
  position: absolute;
  bottom: 6px;
  right: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  color: var(--r-color-overlay-fg);
  box-shadow: var(--r-elev-1);
}

.related-card__name {
  font-size: 11.5px;
  color: var(--r-color-fg-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.3;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}
.related-card:hover .related-card__name {
  color: var(--r-color-fg);
}
</style>
