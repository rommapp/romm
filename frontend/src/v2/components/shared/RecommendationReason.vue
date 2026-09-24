<script setup lang="ts">
// The caption under a recommended game card, shared by the Home row and the
// game-details "Similar games" section. Renders nothing with no reason.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SimilarityReasonSchema } from "@/__generated__";
import { reasonIcon, reasonLabel } from "@/v2/utils/similarityReasons";

const props = defineProps<{
  reasons: SimilarityReasonSchema[];
  // Captions the card in place of the first facet.
  seedRomName?: string | null;
}>();

const { t } = useI18n();

// The sentence goes in the tooltip; it does not fit the cover's width.
const caption = computed(() => {
  if (props.seedRomName) {
    return {
      icon: "mdi-play",
      text: props.seedRomName,
      title: t("recommendations.because-you-played", [props.seedRomName]),
    };
  }

  const reason = props.reasons[0];
  if (!reason) return null;

  return {
    icon: reasonIcon(reason),
    text: reasonLabel(reason, t),
    title: t("recommendations.why"),
  };
});
</script>

<template>
  <span v-if="caption" class="rec-reason" :title="caption.title">
    <RIcon class="rec-reason__icon" :icon="caption.icon" size="11" />
    <span class="rec-reason__text">{{ caption.text }}</span>
  </span>
</template>

<style scoped>
.rec-reason {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  /* Pinned to the cover's width the way GameCard pins its own label, rather
     than to the card-width token, which GameCard overrides on itself. */
  width: 0;
  min-width: 100%;
  max-width: 100%;
  overflow: hidden;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-faint);
  white-space: nowrap;
}

/* The caption is a flex container, so the ellipsis has to live on a real
   child: an anonymous text run never truncates, it just gets cut off. */
.rec-reason__text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rec-reason__icon {
  /* MDI glyphs center on the em box, leaving them ~2px below the text's
     optical center. A transform, because centering absorbs half of a margin. */
  transform: translateY(-1px);
}
</style>
