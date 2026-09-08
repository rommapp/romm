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
  // Takes the place of the facet chip where the feed knows the seed game,
  // e.g. "Because you played Super Metroid".
  label?: string | null;
}>();

const { t } = useI18n();

const reason = computed(() =>
  props.label ? null : (props.reasons[0] ?? null),
);
</script>

<template>
  <span
    v-if="label || reason"
    class="rec-reason"
    :title="t('recommendations.why')"
  >
    <template v-if="label">{{ label }}</template>
    <template v-else-if="reason">
      <RIcon :icon="reasonIcon(reason)" size="11" />
      {{ reasonLabel(reason, t) }}
    </template>
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
  overflow: hidden;
  font-size: 10.5px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-faint);
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
