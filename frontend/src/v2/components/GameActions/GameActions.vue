<script setup lang="ts">
// GameActions — the action row in the game-details header.
// Composes GameActionBtn atoms that are shared with the GameCard hover
// overlay so both surfaces stay visually and behaviourally in sync.
// The Play button uses the emphasized + withLabel variant to match the
// original white pill CTA; every other button is a circular glass icon
// button. The `more` action opens the shared GameActionsList.
//
// Right-side group (desktop only): completion + rating + difficulty
// pickers, separated from the main ribbon by a spacer. All three share
// MetricMenuBtn — the rating/difficulty trigger an RRating popup,
// completion triggers an RSlider popup. On phones these move into the
// status button's sheet (GameActionBtn `withMetrics`) to save a row.
// Writes are optimistic via useGameActions.setScore.
import { computed, ref, toRef } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import MetricMenuBtn from "@/v2/components/GameActions/MetricMenuBtn.vue";
import { METRICS } from "@/v2/components/GameActions/metrics";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useGameActions } from "@/v2/composables/useGameActions";
import { useGridNav } from "@/v2/composables/useGridNav";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
}>();

const { t } = useI18n();
const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);

// Shrink the ribbon on phones — the large (44px) buttons crowd the narrow
// column; the default (36px) size fits more per row and reads cleaner.
const { smAndDown } = useBreakpoint();
const btnSize = computed<"default" | "large">(() =>
  smAndDown.value ? "default" : "large",
);

// Single-row gamepad/keyboard nav across the action ribbon. The root is
// itself the row; cells are every action button (`.r-v2-game-btn`) plus
// the right-side metrics (`.r-v2-metric-btn`), skipping the layout
// spacer. On pad-modality autofocus, `focusFirst` lands on the first
// rendered button — Play if available (template renders it first when
// `canPlay`), otherwise Download.
const rootEl = ref<HTMLElement | null>(null);
useGridNav(rootEl, {
  getRows: () => (rootEl.value ? [rootEl.value] : []),
  getCells: (row) =>
    Array.from(
      row.querySelectorAll<HTMLElement>(".r-v2-game-btn, .r-v2-metric-btn"),
    ),
});
</script>

<template>
  <div ref="rootEl" class="game-actions">
    <GameActionBtn
      v-if="actions.canPlay.value"
      :rom="rom"
      action="play"
      :size="btnSize"
      variant="emphasized"
      with-label
    />
    <div v-if="actions.canPlay.value" class="game-actions__break" />
    <GameActionBtn
      :rom="rom"
      action="download"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="copy-link"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      v-if="actions.canShareQR.value"
      :rom="rom"
      action="qr"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      v-if="actions.canOpenInFlashpoint.value"
      :rom="rom"
      action="flashpoint"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="favorite"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="collection"
      :size="btnSize"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="status"
      :size="btnSize"
      variant="surface"
      with-metrics
    />
    <GameActionBtn :rom="rom" action="more" :size="btnSize" variant="surface" />

    <!-- Desktop only: the metric pills sit in the ribbon. On phones they
         move into the status sheet (see the status button's `withMetrics`). -->
    <template v-if="rom.rom_user && !smAndDown">
      <div class="game-actions__spacer" />
      <MetricMenuBtn
        v-for="m in METRICS"
        :key="m.field"
        :kind="m.kind"
        :label="t(m.labelKey)"
        :icon-full="m.iconFull"
        :icon-empty="m.iconEmpty"
        :accent="m.accent"
        :step="m.step"
        :size="btnSize"
        :value="rom.rom_user?.[m.field] ?? 0"
        @update:value="(v) => actions.setScore(m.field, v)"
      />
    </template>
  </div>
</template>

<style scoped>
.game-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 6px 0 4px;
  flex-wrap: wrap;
}
.game-actions__spacer {
  flex: 1;
  min-width: 16px;
}

/* Mobile: centre the ribbon. The metrics move into the status sheet on
   phones (they aren't rendered here), so no spacer/hairline is needed. */
html[data-bp~="sm-and-down"] .game-actions {
  justify-content: center;
  gap: 8px;
}
/* Full-width break after the Play CTA so it keeps its natural width but
   sits alone (centred) on its own row above the icon ribbon on phones.
   Collapsed on wider viewports so it has no effect there. */
.game-actions__break {
  display: none;
}
html[data-bp~="sm-and-down"] .game-actions__break {
  display: block;
  flex: 0 0 100%;
  height: 0;
}
</style>
