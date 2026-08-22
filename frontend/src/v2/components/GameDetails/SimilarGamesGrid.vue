<script setup lang="ts">
// SimilarGamesGrid — the "Similar games" section of the overview tab.
//
// Unlike RelatedGamesGrid, which renders IGDB's related-game stubs and
// cross-references each one against the library on mount, every entry here
// is already a real ROM resolved server-side by the recommendations index.
// That means normal interactive GameCards (no synthetic rom, no per-card
// request) and a reason chip explaining why each game was suggested.
import { RIcon } from "@v2/lib";
import { useI18n } from "vue-i18n";
import type { SimilarRomSchema } from "@/__generated__";
import GameCard from "@/v2/components/GameCard/GameCard.vue";
import {
  primaryReason,
  reasonIcon,
  reasonLabel,
} from "@/v2/utils/similarityReasons";

defineOptions({ inheritAttrs: false });

defineProps<{
  items: SimilarRomSchema[];
  webp?: boolean;
}>();

const { t } = useI18n();
</script>

<template>
  <div class="similar-games">
    <div
      v-for="item in items"
      :key="`sim-${item.rom.id}`"
      class="similar-games__item"
    >
      <GameCard :rom="item.rom" :webp="webp" />
      <span
        v-if="primaryReason(item.reasons)"
        class="similar-games__reason"
        :title="t('recommendations.why')"
      >
        <RIcon :icon="reasonIcon(primaryReason(item.reasons)!)" size="11" />
        {{ reasonLabel(primaryReason(item.reasons)!, t) }}
      </span>
    </div>
  </div>
</template>

<style scoped>
/* Flex-wrap rather than an auto-fill grid: GameCard is a fixed 158px wide
   and never shrinks, so a `1fr` track would compute below that on narrow
   viewports and push the cards into a horizontal overflow. Horizontal
   padding leaves room for the cover hover-scale before the surrounding
   scroll container clips it. */
.similar-games {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
  padding: 6px 6px 4px;
}

.similar-games__item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.similar-games__reason {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 158px;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-faint);
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
