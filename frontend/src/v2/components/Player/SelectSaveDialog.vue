<script setup lang="ts">
// v2 SelectSaveDialog: lists the ROM's saves on `selectSaveDialog` and emits
// `saveSelected`, through the launch screen's list so a save reads the same.
import { RBtn, RDialog } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AssetList from "@/v2/components/shared/AssetList.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import type { Asset } from "@/v2/utils/assets";

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

function onSelect(asset: Asset) {
  emitter?.emit("saveSelected", asset as SaveSchema);
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
      <AssetList
        :assets="rom?.user_saves ?? []"
        type="save"
        :scrollable="false"
        @select="onSelect"
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
