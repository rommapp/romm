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
  <v-app-bar
    v-if="showSortBar"
    id="gallery-app-bar-sort"
    elevation="0"
    density="compact"
  >
    <v-select hide-details label="Release date"></v-select>
    <v-select hide-details label="IGDB Score"></v-select>
  </v-app-bar>
</template>
