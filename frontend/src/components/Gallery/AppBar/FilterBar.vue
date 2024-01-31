<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

// Props
const showFilterBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("filterBarShow", () => {
  showFilterBar.value = !showFilterBar.value;
});
</script>

<template>
  <v-app-bar
    v-if="showFilterBar"
    id="gallery-app-bar-filter"
    elevation="0"
    density="compact"
  >
    <v-btn
      rounded="0"
      variant="text"
      class="ml-0"
      icon="mdi-file-find-outline"
      title="Show unmatched games"
    />
    <v-select hide-details label="Genre"></v-select>
    <v-select hide-details label="Publisher"></v-select>
    <v-select hide-details label="Developer"></v-select>
    <v-select hide-details label="Theme"></v-select>
    <v-select hide-details label="Series"></v-select>
    <v-select hide-details label="Franchises"></v-select>
  </v-app-bar>
</template>
