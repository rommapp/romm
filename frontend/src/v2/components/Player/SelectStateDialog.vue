<script setup lang="ts">
// v2 SelectStateDialog — same pattern as SelectSaveDialog, but listens for
// `selectStateDialog` and emits `stateSelected`.
import { RBtn, RDialog, RIcon } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AssetCard from "@/v2/components/Player/AssetCard.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);

const emitter = inject<Emitter<Events>>("emitter");
const openHandler = (selectedRom: DetailedRom) => {
  rom.value = selectedRom;
  show.value = true;
};
emitter?.on("selectStateDialog", openHandler);
onBeforeUnmount(() => emitter?.off("selectStateDialog", openHandler));

function onCardClick(state: StateSchema) {
  if (!state) return;
  emitter?.emit("stateSelected", state);
  closeDialog();
}

function closeDialog() {
  show.value = false;
  rom.value = null;
  window.EJS_emulator?.play();
}
</script>

<template>
  <RDialog
    id="select-state-dialog"
    v-model="show"
    icon="mdi-file-outline"
    scroll-content
    :width="mdAndUp ? '56vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("play.select-state") }}</span>
    </template>
    <template #content>
      <div v-if="rom && rom.user_states.length > 0" class="r-v2-state-picker">
        <AssetCard
          v-for="state in rom.user_states"
          :key="state.id"
          :asset="state"
          type="state"
          class="r-v2-state-picker__item"
          @click="onCardClick(state)"
        />
      </div>
      <div v-else class="r-v2-state-picker__empty">
        <RIcon icon="mdi-help-rhombus-outline" size="48" />
        <p>{{ t("rom.no-states-found") }}</p>
      </div>
    </template>
    <template #footer>
      <div style="flex: 1" />
      <RBtn variant="text" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-state-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  padding: 4px;
}

.r-v2-state-picker__item {
  cursor: pointer;
}

.r-v2-state-picker__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 0;
  color: var(--r-color-fg-muted);
}
.r-v2-state-picker__empty p {
  margin: 0;
  font-size: 14px;
}
</style>
