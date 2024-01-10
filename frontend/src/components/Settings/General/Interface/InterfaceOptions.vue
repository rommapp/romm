<script setup lang="ts">
import { ref } from "vue";
import { isUndefined } from "lodash";

const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRoms = ref(
  isUndefined(storedGroupRoms) ? true : storedGroupRoms === "true"
);

// Functions
function toggleGroupRoms() {
  localStorage.setItem("settings.groupRoms", groupRoms.value.toString());
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

    <v-card-text>
      <v-row no-gutters class="align-center">
        <v-col cols="8" lg="4" class="d-flex">
          <v-icon
            :class="groupRoms ? 'text-romm-accent-1' : ''"
            :icon="groupRoms ? 'mdi-group' : 'mdi-ungroup'"
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="groupRoms ? 'text-romm-accent-1' : ''"
              >Group roms</span
            >
            <p class="mt-1">
              Group versions of the same rom together in the gallery
            </p>
          </div>
        </v-col>
        <v-col cols="4">
          <v-switch
            class="ml-10"
            v-model="groupRoms"
            color="romm-accent-1"
            @update:model-value="toggleGroupRoms"
            hide-details
          ></v-switch>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
