<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import type { StateSchema } from "@/__generated__";
import EmptySates from "@/components/common/EmptyStates/EmptyStates.vue";
import AssetCard from "@/components/common/Game/AssetCard.vue";
import storeAuth from "@/stores/auth";
import { type DetailedRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";

const auth = storeAuth();
const { scopes } = storeToRefs(auth);
const props = defineProps<{ rom: DetailedRom }>();
const selectedStates = ref<StateSchema[]>([]);
const lastSelectedIndex = ref<number>(-1);
const emitter = inject<Emitter<Events>>("emitter");

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
  <v-row class="my-2 mx-4" no-gutters>
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
          size="small"
          @click="
            emitter?.emit('showDeleteStatesDialog', {
              rom: props.rom,
              states: selectedStates,
            })
          "
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </v-btn-group>
    </v-col>
  </v-row>
  <v-row v-if="rom.user_states.length > 0" class="my-2 mx-4" no-gutters>
    <v-col
      v-for="state in rom.user_states"
      :key="state.id"
      cols="6"
      sm="4"
      class="pa-1 align-self-end"
    >
      <AssetCard
        :asset="state"
        type="state"
        :selected="selectedStates.some((s) => s.id === state.id)"
        :rom="props.rom"
        :scopes="scopes"
        @click="(e: MouseEvent) => onCardClick(state, e)"
      />
    </v-col>
  </v-row>
  <EmptySates v-else />
</template>
