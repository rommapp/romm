<script setup lang="ts">
// GameActions — the action row in the game-details header.
// Composes GameActionBtn atoms that are shared with the GameCard hover
// overlay so both surfaces stay visually and behaviourally in sync.
// The Play button uses the emphasized + withLabel variant to match the
// original white pill CTA; every other button is a circular glass icon
// button. The `more` action opens the shared GameActionsList.
//
// Right-side group: completion + rating + difficulty pickers, separated
// from the main ribbon by a spacer. All three share MetricMenuBtn — the
// rating/difficulty trigger an RRating popup, completion triggers an
// RSlider popup. Writes are optimistic via useGameActions.setScore.
import { computed, ref, toRef } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import MetricMenuBtn from "@/v2/components/GameActions/MetricMenuBtn.vue";
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
    />
    <GameActionBtn :rom="rom" action="more" :size="btnSize" variant="surface" />

    <div v-if="rom.rom_user" class="game-actions__spacer" />

    <MetricMenuBtn
      v-if="rom.rom_user"
      kind="percent"
      :label="t('rom.metric-completion')"
      icon-full="mdi-progress-check"
      icon-empty="mdi-progress-helper"
      accent="brand-primary"
      :step="5"
      :size="btnSize"
      :value="rom.rom_user.completion ?? 0"
      @update:value="(v) => actions.setScore('completion', v)"
    />
    <MetricMenuBtn
      v-if="rom.rom_user"
      :label="t('rom.metric-rating')"
      icon-full="mdi-star"
      icon-empty="mdi-star-outline"
      accent="warning"
      :size="btnSize"
      :value="rom.rom_user.rating"
      @update:value="(v) => actions.setScore('rating', v)"
    />
    <MetricMenuBtn
      v-if="rom.rom_user"
      :label="t('rom.metric-difficulty')"
      icon-full="mdi-chili-mild"
      icon-empty="mdi-chili-mild-outline"
      accent="danger"
      :size="btnSize"
      :value="rom.rom_user.difficulty"
      @update:value="(v) => actions.setScore('difficulty', v)"
    />
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

/* Mobile: centre the ribbon and force the metrics (completion / rating /
   difficulty) onto their own row, split from the action buttons by a
   full-width hairline so the two groups read as distinct sections. */
html[data-bp~="sm-and-down"] .game-actions {
  justify-content: center;
  gap: 8px;
}
html[data-bp~="sm-and-down"] .game-actions__spacer {
  flex: 0 0 100%;
  min-width: 0;
  height: 0;
  margin: 6px 0 2px;
  border-top: 1px solid var(--r-color-border);
}
</style>
