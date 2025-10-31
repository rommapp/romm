<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import type { SaveSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";

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
    icon="mdi-format-wrap-square"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <span class="text-h5 ml-4">{{ t("play.select-save") }}</span>
    </template>
    <template #content>
      <div v-if="rom" class="d-flex justify-center ga-4 flex-md-wrap py-6 px-2">
        <v-card
          v-for="save in rom.user_saves"
          v-if="rom.user_saves.length > 0"
          :key="save.id"
          class="bg-toplayer transform-scale"
          width="200px"
          @click="onCardClick(save)"
        >
          <v-card-text
            class="d-flex flex-column justify-end h-100"
            style="padding: 1.5rem"
          >
            <v-row>
              <v-img
                cover
                height="100%"
                min-height="75px"
                :src="
                  save.screenshot?.download_path ??
                  getEmptyCoverImage(save.file_name)
                "
              />
            </v-row>
            <v-row class="mt-6 flex-grow-0">
              {{ save.file_name }}
            </v-row>
            <v-row
              class="mt-6 d-flex flex-md-wrap ga-2 flex-grow-0"
              style="min-height: 20px"
            >
              <v-chip v-if="save.emulator" size="x-small" color="orange" label>
                {{ save.emulator }}
              </v-chip>
              <v-chip size="x-small" label>
                {{ formatBytes(save.file_size_bytes) }}
              </v-chip>
              <v-chip size="x-small" label>
                Updated: {{ formatTimestamp(save.updated_at) }}
              </v-chip>
            </v-row>
          </v-card-text>
        </v-card>
        <div v-else>
          <v-col class="text-center mt-6">
            <v-icon size="x-large"> mdi-help-rhombus-outline </v-icon>
            <p class="text-h4 mt-2">
              {{ t("rom.no-states-found") }}
            </p>
          </v-col>
        </div>
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
