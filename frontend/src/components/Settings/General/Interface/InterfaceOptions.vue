<script setup lang="ts">
import { ref } from "vue";
import { isUndefined } from "lodash";

const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRoms = ref(isUndefined(storedGroupRoms) ? true : storedGroupRoms === "true");

// Functions
function toggleGroupRoms() {
  localStorage.setItem("settings.groupRoms", groupRoms.value);
}
</script>

<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-palette-swatch-outline</v-icon>
        Interface
      </v-toolbar-title>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text class="pa-3">
      <v-row>
        <v-col cols="6">
          <span class="font-weight-bold text-body-1">Group roms</span>
          <p class="mt-1">
            Group versions of the same rom together in the gallery
          </p>
        </v-col>
        <v-col cols="6" class="text-right">
          <v-switch
            v-model="groupRoms"
            color="romm-accent-1"
            @update:model-value="toggleGroupRoms"
          ></v-switch>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
