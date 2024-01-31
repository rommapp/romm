<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const showSortBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("sortBarShow", () => {
  showSortBar.value = !showSortBar.value;
});
</script>

<template>
  <template v-if="showSortBar">
    <v-divider class="my-0" />
    <div
      class="px-1 py-2"
      id="gallery-app-bar-sort"
      elevation="0"
      density="compact"
    >
      <v-row no-gutters>
        <v-col cols="6" sm="6" md="6" lg="6" xl="6">
          <v-select
            hide-details
            label="Release date"
            density="compact"
            variant="outlined"
            class="pa-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="6" md="6" lg="6" xl="6">
          <v-select
            hide-details
            label="IGDB Score"
            density="compact"
            variant="outlined"
            class="pa-1"
          ></v-select>
        </v-col>
      </v-row>
    </div>
    <v-divider class="my-0" />
  </template>
</template>
