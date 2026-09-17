<script setup lang="ts">
// v2 SelectStateDialog — same pattern as SelectSaveDialog, but listens for
// `selectStateDialog` and emits `stateSelected`.
import { RBtn, RDialog, REmptyState } from "@v2/lib";
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
      <REmptyState
        v-else
        icon="mdi-help-rhombus-outline"
        :title="t('rom.no-states-found')"
      />
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
</style>
