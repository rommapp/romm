<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const { mdAndUp } = useDisplay();
const show = ref(false);
const rom = ref<DetailedRom | null>(null);

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("selectStateDialog", (selectedRom) => {
  rom.value = selectedRom;
  show.value = true;
});

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
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-format-wrap-square"
    scroll-content
    :width="mdAndUp ? '50vw' : '95vw'"
    id="select-state-dialog"
  >
    <template #header>
      <span class="text-h5 ml-4">{{ t("play.select-state") }}</span>
    </template>
    <template #content>
      <div v-if="rom" class="d-flex justify-center ga-4 flex-md-wrap py-6 px-2">
        <v-hover
          v-if="rom.user_states.length > 0"
          v-for="state in rom.user_states"
          v-slot="{ isHovering, props }"
        >
          <v-card
            v-bind="props"
            class="bg-toplayer transform-scale"
            :class="{
              'on-hover': isHovering,
            }"
            :elevation="isHovering ? 20 : 3"
            width="200px"
            @click="onCardClick(state)"
          >
            <v-card-text
              class="d-flex flex-column justify-end h-100"
              style="padding: 1.5rem"
            >
              <v-row>
                <v-img
                  cover
                  height="100%"
                  :src="
                    state.screenshot?.download_path ??
                    getEmptyCoverImage(state.file_name)
                  "
                />
              </v-row>
              <v-row class="mt-6 flex-grow-0">{{ state.file_name }}</v-row>
              <v-row
                class="mt-6 d-flex flex-md-wrap ga-2 flex-grow-0"
                style="min-height: 20px"
              >
                <v-chip
                  v-if="state.emulator"
                  size="x-small"
                  color="orange"
                  label
                >
                  {{ state.emulator }}
                </v-chip>
                <v-chip size="x-small" label>
                  {{ formatBytes(state.file_size_bytes) }}
                </v-chip>
                <v-chip size="x-small" label>
                  {{ formatTimestamp(state.updated_at) }}
                </v-chip>
              </v-row>
            </v-card-text>
          </v-card>
        </v-hover>
        <div v-else>
          <v-col class="text-center mt-6">
            <v-icon size="x-large">mdi-help-rhombus-outline</v-icon>
            <p class="text-h4 mt-2">{{ t("rom.no-states-found") }}</p>
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
  </r-dialog>
</template>
