<script setup lang="ts">
// GameMetricsSections: the three per-user metric editors (completion,
// rating, difficulty) stacked as sections under a "Your progress"
// header. Mounted inside the Status button's mobile sheet (see
// GameActionBtn `withMetrics`) so phones edit scores there instead of
// via the desktop ribbon pills. Writes via useGameActions.setScore.
import { RDivider, RSectionLabel } from "@v2/lib";
import { toRef } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import MetricSection from "@/v2/components/GameActions/MetricSection.vue";
import { METRICS } from "@/v2/components/GameActions/metrics";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const props = defineProps<{ rom: SimpleRom }>();

const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);
</script>

<template>
  <div class="game-metrics">
    <RSectionLabel as="p" class="game-metrics__title">{{
      t("rom.your-progress")
    }}</RSectionLabel>
    <template v-for="(m, i) in METRICS" :key="m.field">
      <RDivider v-if="i > 0" />
      <MetricSection
        :kind="m.kind"
        :value="rom.rom_user?.[m.field] ?? 0"
        :label="t(m.labelKey)"
        :icon-full="m.iconFull"
        :icon-empty="m.iconEmpty"
        :accent="m.accent"
        :step="m.step"
        @update:value="(v) => actions.setScore(m.field, v)"
      />
    </template>
  </div>
</template>

<style scoped>
.game-metrics {
  display: flex;
  flex-direction: column;
}
.game-metrics__title {
  padding: 8px 14px 2px;
}
</style>
