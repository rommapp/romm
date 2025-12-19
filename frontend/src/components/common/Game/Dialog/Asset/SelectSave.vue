<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import type { SaveSchema } from "@/__generated__";
import AssetCard from "@/components/common/Game/AssetCard.vue";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const { mdAndUp } = useDisplay();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("selectSaveDialog", (selectedRom) => {
  rom.value = selectedRom;
  show.value = true;
});

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
    icon="mdi-file-outline"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row no-gutters class="justify-center">
        <span>{{ t("play.select-save") }}</span>
      </v-row>
    </template>
    <template #content>
      <v-row
        v-if="rom && rom.user_saves.length > 0"
        class="align-content-start pa-2"
        no-gutters
      >
        <v-col
          v-for="save in rom.user_saves"
          class="pa-1 align-self-end"
          cols="3"
        >
          <AssetCard
            :asset="save"
            type="save"
            :rom="rom"
            :show-hover-actions="false"
            @click="onCardClick(save)"
          />
        </v-col>
      </v-row>
      <div v-else class="text-center mt-6">
        <v-icon size="x-large"> mdi-help-rhombus-outline </v-icon>
        <p class="text-h4 mt-2">
          {{ t("rom.no-states-found") }}
        </p>
      </div>
    </template>
    <template #append>
      <v-row class="justify-center my-2">
        <v-btn class="bg-toplayer" variant="flat" @click="closeDialog">
          Cancel
        </v-btn>
      </v-row>
    </template>
  </RDialog>
</template>
