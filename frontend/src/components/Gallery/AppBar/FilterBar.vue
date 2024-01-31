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
  <template v-if="showFilterBar">
    <div
      class="px-1 py-2"
      id="gallery-app-bar-filter"
      elevation="0"
      density="compact"
    >
      <v-row no-gutters>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Genre"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Publisher"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Developer"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Theme"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Series"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
        <v-col cols="6" sm="" md="" lg="4" xl="3">
          <v-select
            hide-details
            label="Franchises"
            density="compact"
            variant="outlined"
            class="ma-1"
          ></v-select>
        </v-col>
      </v-row>
    </div>
    <v-divider
      class="my-0 mx-2 border-opacity-25"
      :thickness="2"
      color="romm-accent-1"
    />
  </template>
</template>
