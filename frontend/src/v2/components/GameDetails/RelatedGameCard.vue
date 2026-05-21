<script setup lang="ts">
// RelatedGameCard — single card in the related-games strip.
// On mount, looks up the game in the local RomM library by IGDB id
// (`getRomByMetadataProvider`). When the lookup hits the card jumps
// to the internal RomM detail page via the router (no full reload);
// when it misses the card falls back to the IGDB game page so the
// user can still reach metadata for games they don't own.
//
// Mirrors v1's per-card pattern (frontend/src/components/common/Game/
// Card/Related.vue) — each card owns its own lookup so the parent
// grid stays a thin renderer. We keep the root as a single `<a>`
// throughout the card's life (not a `<RouterLink>` ↔ `<a>` swap)
// because RTooltip resolves its reference from the slot's first
// element on mount: swapping that element on resolution would leave
// the tooltip anchored to a detached node and float into the
// top-left of the viewport.
import { RIcon, RTooltip } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import type { IGDBRelatedGame } from "@/__generated__";
import romApi from "@/services/api/rom";

defineOptions({ inheritAttrs: false });

const props = defineProps<{ game: IGDBRelatedGame }>();

const router = useRouter();
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

const href = computed(() =>
  inLibrary.value
    ? `/rom/${romId.value}`
    : `https://www.igdb.com/games/${props.game.slug}`,
);
const target = computed(() => (inLibrary.value ? undefined : "_blank"));
const rel = computed(() =>
  inLibrary.value ? undefined : "noopener noreferrer",
);

// Modifier-key + middle-click escape so the user can still open the
// internal link in a new tab; otherwise route internally via the
// router so the SPA stays single-load.
function onClick(e: MouseEvent) {
  if (!inLibrary.value) return;
  if (e.defaultPrevented) return;
  if (e.button !== 0) return;
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  e.preventDefault();
  void router.push(href.value);
}
</script>

<template>
  <RTooltip :text="game.name" location="top" :open-delay="400">
    <template #activator="{ props: activatorProps }">
      <a
        v-bind="activatorProps"
        :href="href"
        :target="target"
        :rel="rel"
        class="related-card"
        :class="{ 'related-card--in-library': inLibrary }"
        @click="onClick"
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

          <!-- In-library affordance — small brand-tinted dot in the
               corner. Subtle enough that it doesn't read as a
               "selected" state but visible enough to scan a strip
               quickly for owned games. -->
          <span v-if="inLibrary" class="related-card__owned" aria-hidden="true">
            <RIcon icon="mdi-check" size="10" />
          </span>
        </div>
        <div class="related-card__name">{{ game.name }}</div>
      </a>
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

/* Tiny "owned" dot — solid brand-coloured circle with a check.
   Sits in the bottom-right of the cover so it reads as a status
   indicator, not a selection chrome. */
.related-card__owned {
  position: absolute;
  bottom: 6px;
  right: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--r-color-brand-primary);
  color: var(--r-color-overlay-fg);
  box-shadow: 0 1px 4px color-mix(in srgb, black 50%, transparent);
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
