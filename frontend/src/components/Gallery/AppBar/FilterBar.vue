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
  <v-expand-transition>
    <div v-if="showFilterBar">
      <v-row no-gutters  class="pt-1 px-1">
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
      <v-divider :thickness="2" class="mx-2 mt-1 border-opacity-25" color="romm-accent-1" />
    </div>
  </v-expand-transition>
</template>
