<script setup lang="ts">
// LoadSaveStateDialog: the in-game Load button's picker, with the launch
// screen's Saves / States tabs. Opens on `selectStateDialog` and emits
// `saveSelected` or `stateSelected`.
import { RBtn, RDialog, RSliderBtnGroup } from "@v2/lib";
import type { Emitter } from "mitt";
import { inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useSaveStateTabs } from "@/v2/composables/useSaveStateTabs";
import type { Asset, AssetType } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);
// States apply on the fly, so they are what the button reaches for first.
const tab = ref<AssetType>("state");

const { tabs, stateDisabledReason } = useSaveStateTabs(
  () => rom.value?.user_saves ?? [],
  () => rom.value?.user_states ?? [],
  () => window.EJS_core,
);

const emitter = inject<Emitter<Events>>("emitter");
const openHandler = (selectedRom: DetailedRom) => {
  rom.value = selectedRom;
  show.value = true;
};
emitter?.on("selectStateDialog", openHandler);
onBeforeUnmount(() => emitter?.off("selectStateDialog", openHandler));

function onSelect(asset: Asset) {
  if (tab.value === "save") emitter?.emit("saveSelected", asset as SaveSchema);
  else emitter?.emit("stateSelected", asset as StateSchema);
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
    id="load-save-state-dialog"
    v-model="show"
    icon="mdi-folder-open-outline"
    scroll-content
    :width="mdAndUp ? '56vw' : '95vw'"
    height="70vh"
    full-height-on-mobile
    @close="closeDialog"
  >
    <template #header>
      <span>{{ t("rom.load-save-or-state") }}</span>
    </template>
    <template #toolbar>
      <div class="r-v2-load-save-state__tabs">
        <RSliderBtnGroup
          v-model="tab"
          variant="tab"
          :items="tabs"
          :aria-label="t('rom.load-save-or-state')"
        />
      </div>
    </template>
    <template #content>
      <div v-if="tab === 'save'" class="r-v2-load-save-state__saves">
        <p class="r-v2-load-save-state__note">
          {{ t("play.load-save-restarts") }}
        </p>
        <AssetList
          :assets="rom?.user_saves ?? []"
          type="save"
          :scrollable="false"
          @select="onSelect"
        />
      </div>
      <AssetStrip
        v-else
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

<style scoped>
.r-v2-load-save-state__tabs {
  display: flex;
  justify-content: center;
}

.r-v2-load-save-state__saves {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-v2-load-save-state__note {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
</style>
