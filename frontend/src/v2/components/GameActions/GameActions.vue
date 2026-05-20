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
import { toRef } from "vue";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "@/v2/components/GameActions/GameActionBtn.vue";
import MetricMenuBtn from "@/v2/components/GameActions/MetricMenuBtn.vue";
import { useGameActions } from "@/v2/composables/useGameActions";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: SimpleRom;
  canPlay: boolean;
}>();

const romRef = toRef(props, "rom");
const actions = useGameActions(() => romRef.value);
</script>

<template>
  <div class="game-actions">
    <GameActionBtn
      v-if="canPlay"
      :rom="rom"
      action="play"
      size="large"
      variant="emphasized"
      with-label
    />
    <GameActionBtn
      :rom="rom"
      action="download"
      size="large"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="copy-link"
      size="large"
      variant="surface"
    />
    <GameActionBtn
      v-if="actions.canShareQR.value"
      :rom="rom"
      action="qr"
      size="large"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="favorite"
      size="large"
      variant="surface"
    />
    <GameActionBtn
      :rom="rom"
      action="collection"
      size="large"
      variant="surface"
    />
    <GameActionBtn :rom="rom" action="status" size="large" variant="surface" />
    <GameActionBtn :rom="rom" action="more" size="large" variant="surface" />

    <div v-if="rom.rom_user" class="game-actions__spacer" />

    <MetricMenuBtn
      v-if="rom.rom_user"
      kind="percent"
      label="Completion"
      icon-full="mdi-progress-check"
      icon-empty="mdi-progress-helper"
      accent="brand-primary"
      :step="5"
      :value="rom.rom_user.completion ?? 0"
      @update:value="(v) => actions.setScore('completion', v)"
    />
    <MetricMenuBtn
      v-if="rom.rom_user"
      label="Rating"
      icon-full="mdi-star"
      icon-empty="mdi-star-outline"
      accent="warning"
      :value="rom.rom_user.rating"
      @update:value="(v) => actions.setScore('rating', v)"
    />
    <MetricMenuBtn
      v-if="rom.rom_user"
      label="Difficulty"
      icon-full="mdi-chili-mild"
      icon-empty="mdi-chili-mild-outline"
      accent="danger"
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
</style>
