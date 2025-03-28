<script setup lang="ts">
import type { StateSchema } from "@/__generated__";
import RDialog from "@/components/common/RDialog.vue";
import type { DetailedRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import { getEmptyCoverImage } from "@/utils/covers";
import type { Emitter } from "mitt";
import { inject, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import { storeToRefs } from "pinia";

// Props
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
    <template #content>
      <div v-if="rom" class="d-flex justify-center ga-4 flex-md-wrap mt-6 px-2">
        <v-hover
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
              <v-row class="position-relative">
                <v-img
                  cover
                  :src="
                    state.screenshot?.download_path ??
                    getEmptyCoverImage(state.file_name)
                  "
                />
                <v-btn-group
                  v-if="isHovering"
                  class="position-absolute bottom-0 right-0"
                  density="compact"
                >
                  <v-btn
                    v-if="scopes.includes('assets.write')"
                    drawer
                    size="small"
                    @click="
                      (e: MouseEvent) => {
                        e.stopPropagation();
                        emitter?.emit('showDeleteStatesDialog', {
                          rom: rom,
                          states: [state],
                        });
                      }
                    "
                  >
                    <v-icon class="text-romm-red">mdi-delete</v-icon>
                  </v-btn>
                </v-btn-group>
              </v-row>
              <v-row class="mt-6 flex-grow-0">{{
                state.file_name.replace(rom.fs_name_no_ext, "")
              }}</v-row>
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
