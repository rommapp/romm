<script setup lang="ts">
// The in-game Load picker with the launch screen's Saves / States tabs: opens
// on `selectStateDialog`, emits `saveSelected` or `stateSelected`.
import { RBtn, RDialog, RSliderBtnGroup } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import AssetList from "@/v2/components/shared/AssetList.vue";
import AssetStrip from "@/v2/components/shared/AssetStrip.vue";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSaveStateTabs } from "@/v2/composables/useSaveStateTabs";
import type { Asset, AssetType } from "@/v2/utils/assets";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const confirm = useConfirm();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);
// States apply on the fly, so they are what the button reaches for first.
const tab = ref<AssetType>("state");

const saves = computed(() => rom.value?.user_saves ?? []);
const states = computed(() => rom.value?.user_states ?? []);
const { tabs, stateDisabledReason } = useSaveStateTabs(
  saves,
  states,
  () => window.EJS_core,
);

const emitter = inject<Emitter<Events>>("emitter");
const openHandler = (selectedRom: DetailedRom) => {
  rom.value = selectedRom;
  tab.value = "state";
  show.value = true;
};
emitter?.on("selectStateDialog", openHandler);
onBeforeUnmount(() => emitter?.off("selectStateDialog", openHandler));

// Either one replaces the running game, so unsaved progress is at stake.
async function onSelect(asset: Asset) {
  const isSave = tab.value === "save";
  const ok = await confirm(
    isSave
      ? {
          title: t("play.load-save-confirm-title"),
          body: t("play.load-save-confirm-body"),
          confirmText: t("play.load-save"),
        }
      : {
          title: t("play.load-state-confirm-title"),
          body: t("play.load-state-confirm-body"),
          confirmText: t("play.load-state"),
        },
  );
  if (!ok) return;
  if (isSave) emitter?.emit("saveSelected", asset as SaveSchema);
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
      <AssetList
        v-if="tab === 'save'"
        :assets="saves"
        type="save"
        :scrollable="false"
        @select="onSelect"
      />
      <AssetStrip
        v-else
        :assets="states"
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
</style>
