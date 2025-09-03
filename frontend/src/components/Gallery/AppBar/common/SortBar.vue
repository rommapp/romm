<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import type { Events } from "@/types/emitter";

const showSortBar = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("sortBarShow", () => {
  showSortBar.value = !showSortBar.value;
});
const sortBy = ["IGDB rating", "Release date"];
const sorted = ref([]);
function sort() {}
</script>

<template>
  <div v-if="showSortBar">
    <v-row no-gutters class="pt-1 px-1">
      <!-- <v-col cols="6" sm="6" md="6" lg="6" xl="6">
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
        </v-col> -->
      <v-col>
        <v-select
          hide-details
          label="Order by"
          density="compact"
          variant="outlined"
          class="pa-1"
          multiple
          chips
          :items="sortBy"
          :model="sorted"
          @update:model-value="sort"
        />
      </v-col>
    </v-row>
    <v-divider
      :thickness="2"
      class="mx-2 mt-1 border-opacity-25"
      color="primary"
    />
  </div>
</template>
