<script setup lang="ts">
// v2 SelectStateDialog — same pattern as SelectSaveDialog, but listens for
// `selectStateDialog` and emits `stateSelected`. The list is the launch
// screen's, so a state reads the same whether it is picked before the game
// boots or from inside it.
import { RBtn, RDialog } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { isCoreCompatible, type Asset } from "@/v2/utils/assets";

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

// A state another core wrote stays listed, disabled, so the count adds up.
function stateDisabledReason(asset: { emulator?: string | null }) {
  if (isCoreCompatible(asset, window.EJS_core)) return null;
  return t("play.state-incompatible-core", { emulator: asset.emulator });
}

function onSelect(asset: Asset) {
  emitter?.emit("stateSelected", asset as StateSchema);
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
      <AssetStrip
        :assets="rom?.user_states ?? []"
        type="state"
        layout="flow"
        group-by="emulator"
        :disabled-reason="stateDisabledReason"
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
