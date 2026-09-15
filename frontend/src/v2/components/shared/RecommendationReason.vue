<script setup lang="ts">
// The caption under a recommended game card, shared by the Home row and the
// game-details "Similar games" section. Renders nothing with no reason.
import { RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { SimilarityReasonSchema } from "@/__generated__";
import { reasonIcon, reasonLabel } from "@/v2/utils/similarityReasons";

const SEED_ICON = "mdi-play";

const props = defineProps<{
  reasons: SimilarityReasonSchema[];
  // Captions the card with the game the recommendation came from, in place
  // of the first facet.
  seedRomName?: string | null;
}>();

const { t } = useI18n();

const reason = computed(() =>
  props.seedRomName ? null : (props.reasons[0] ?? null),
);

const icon = computed(() => {
  if (props.seedRomName) return SEED_ICON;
  return reason.value ? reasonIcon(reason.value) : null;
});

const text = computed(() => {
  if (props.seedRomName) return props.seedRomName;
  return reason.value ? reasonLabel(reason.value, t) : null;
});

// The seed name alone fits the card where the full sentence never did, so
// the sentence lives here.
const title = computed(() =>
  props.seedRomName
    ? t("recommendations.because-you-played", [props.seedRomName])
    : t("recommendations.why"),
);
</script>

<template>
  <span v-if="text" class="rec-reason" :title="title">
    <RIcon v-if="icon" class="rec-reason__icon" :icon="icon" size="11" />
    <span class="rec-reason__text">{{ text }}</span>
  </span>
</template>

<style scoped>
.rec-reason {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  /* Clip to the card it captions rather than widening the row's scroll
     track; the token tracks the per-breakpoint card width. */
  max-width: var(--r-card-art-w);
  /* Centres the caption under the card's centred title. Auto margins, not
     `justify-content`, so an over-long caption still truncates from one end. */
  margin-inline: auto;
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
  /* MDI glyphs centre on the em box, which the text's descender space drops
     ~2px below its optical centre. Transform, not margin: centring absorbs
     half of a margin, and a whole pixel stays crisp at 1x. */
  transform: translateY(-1px);
}
</style>
