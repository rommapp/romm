<script setup lang="ts">
// v2 SelectSaveDialog — listens for `selectSaveDialog`, shows a grid of
// the ROM's saves and emits `saveSelected` on click (consumed by the
// EmulatorJS view).
import { RBtn, RDialog, REmptyState } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema } from "@/__generated__";
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
emitter?.on("selectSaveDialog", openHandler);
onBeforeUnmount(() => emitter?.off("selectSaveDialog", openHandler));

function onCardClick(save: SaveSchema) {
  if (!save) return;
  emitter?.emit("saveSelected", save);
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
    id="select-save-dialog"
    v-model="show"
    icon="mdi-content-save-outline"
    scroll-content
    :width="mdAndUp ? '56vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("play.select-save") }}</span>
    </template>
    <template #content>
      <div v-if="rom && rom.user_saves.length > 0" class="r-v2-save-picker">
        <AssetCard
          v-for="save in rom.user_saves"
          :key="save.id"
          :asset="save"
          type="save"
          class="r-v2-save-picker__item"
          @click="onCardClick(save)"
        />
      </div>
      <REmptyState
        v-else
        icon="mdi-help-rhombus-outline"
        :title="t('rom.no-saves-found')"
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
.r-v2-save-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  padding: 4px;
}

.r-v2-save-picker__item {
  cursor: pointer;
}
</style>
