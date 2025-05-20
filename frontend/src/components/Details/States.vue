<script setup lang="ts">
import EmptySates from "@/components/common/EmptyStates/EmptyStates.vue";
import type { StateSchema } from "@/__generated__";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { formatBytes, formatTimestamp } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";
import { getEmptyCoverImage } from "@/utils/covers";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const props = defineProps<{ rom: DetailedRom }>();
const selectedStates = ref<StateSchema[]>([]);
const lastSelectedIndex = ref<number>(-1);
const emitter = inject<Emitter<Events>>("emitter");

// Functions
async function downloasStates() {
  selectedStates.value.map((state) => {
    const a = document.createElement("a");
    a.href = state.download_path;
    a.download = `${state.file_name}`;
    a.click();
  });

  selectedStates.value = [];
}

function onCardClick(state: StateSchema, event: MouseEvent) {
  const stateIndex = props.rom.user_states.indexOf(state);

  if (event.shiftKey && lastSelectedIndex.value !== null) {
    const [startIndex, endIndex] = [lastSelectedIndex.value, stateIndex].sort(
      (a, b) => a - b,
    );
    const rangeStates = props.rom.user_states.slice(startIndex, endIndex + 1);

    const isDeselecting = selectedStates.value.includes(state);

    if (isDeselecting) {
      selectedStates.value = selectedStates.value.filter(
        (s) => !rangeStates.includes(s),
      );
    } else {
      const statesToAdd = rangeStates.filter(
        (s) => !selectedStates.value.includes(s),
      );
      selectedStates.value = [...selectedStates.value, ...statesToAdd];
    }
  } else {
    const isSelected = selectedStates.value.includes(state);

    if (isSelected) {
      selectedStates.value = selectedStates.value.filter(
        (s) => s.id !== state.id,
      );
    } else {
      selectedStates.value = [...selectedStates.value, state];
    }
  }

  lastSelectedIndex.value = stateIndex;
}
</script>

<template>
  <v-row class="ma-2" no-gutters>
    <v-col class="pa-1">
      <v-btn-group divided density="default">
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
          size="small"
          @click="emitter?.emit('addStatesDialog', rom)"
        >
          <v-icon>mdi-cloud-upload-outline</v-icon>
        </v-btn>
        <v-btn
          drawer
          :disabled="!selectedStates.length"
          :variant="selectedStates.length > 0 ? 'flat' : 'plain'"
          size="small"
          @click="downloasStates"
        >
          <v-icon>mdi-download</v-icon>
        </v-btn>
        <v-btn
          v-if="scopes.includes('assets.write')"
          drawer
          :class="{
            'text-romm-red': selectedStates.length,
          }"
          :disabled="!selectedStates.length"
          :variant="selectedStates.length > 0 ? 'flat' : 'plain'"
          @click="
            emitter?.emit('showDeleteStatesDialog', {
              rom: props.rom,
              states: selectedStates,
            })
          "
          size="small"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </v-btn-group>
    </v-col>
  </v-row>
  <v-row v-if="rom.user_states.length > 0" class="ma-2" no-gutters>
    <v-col cols="6" sm="4" class="pa-1" v-for="state in rom.user_states">
      <v-hover v-slot="{ isHovering, props }">
        <v-card
          v-bind="props"
          class="bg-toplayer transform-scale"
          :class="{
            'on-hover': isHovering,
            'border-selected': selectedStates.some((s) => s.id === state.id),
          }"
          :elevation="isHovering ? 20 : 3"
          @click="(e) => onCardClick(state, e)"
        >
          <v-card-text class="pa-2">
            <v-row no-gutters>
              <v-col cols="12">
                <v-img
                  rounded
                  :src="
                    state.screenshot?.download_path ??
                    getEmptyCoverImage(state.file_name)
                  "
                >
                  <v-slide-x-transition>
                    <v-btn-group
                      v-if="isHovering"
                      class="position-absolute"
                      density="compact"
                      style="bottom: 4px; right: 4px"
                    >
                      <v-btn
                        drawer
                        :href="state.download_path"
                        download
                        size="small"
                      >
                        <v-icon>mdi-download</v-icon>
                      </v-btn>
                      <v-btn
                        v-if="scopes.includes('assets.write')"
                        drawer
                        size="small"
                        @click="
                          emitter?.emit('showDeleteStatesDialog', {
                            rom: props.rom,
                            states: [state],
                          })
                        "
                      >
                        <v-icon class="text-romm-red">mdi-delete</v-icon>
                      </v-btn>
                    </v-btn-group>
                  </v-slide-x-transition>
                </v-img>
              </v-col>
            </v-row>
            <v-row class="py-2 text-caption" no-gutters>{{
              state.file_name
            }}</v-row>
            <v-row class="ga-1" no-gutters>
              <v-col v-if="state.emulator" cols="12">
                <v-chip size="x-small" color="orange" label>
                  {{ state.emulator }}
                </v-chip>
              </v-col>
              <v-col cols="12">
                <v-chip size="x-small" label>
                  {{ formatBytes(state.file_size_bytes) }}
                </v-chip>
              </v-col>
              <v-col cols="12">
                <v-chip size="x-small" label>
                  Updated: {{ formatTimestamp(state.updated_at) }}
                </v-chip>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>
      </v-hover>
    </v-col>
  </v-row>
  <empty-sates v-else />
</template>
