<script setup lang="ts">
import { isNull } from "lodash";
import { ref } from "vue";

const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRomsRef = ref(
  isNull(storedGroupRoms) ? true : storedGroupRoms === "true"
);
const storedRegions = localStorage.getItem("settings.showRegions");
const regionsRef = ref(isNull(storedRegions) ? true : storedRegions === "true");
const storedLanguages = localStorage.getItem("settings.showLanguages");
const languagesRef = ref(
  isNull(storedLanguages) ? true : storedLanguages === "true"
);
const storedSiblings = localStorage.getItem("settings.showSiblings");
const siblingsRef = ref(
  isNull(storedSiblings) ? true : storedSiblings === "true"
);

// Functions
function toggleGroupRoms() {
  localStorage.setItem("settings.groupRoms", groupRomsRef.value.toString());
}
function toggleRegions() {
  localStorage.setItem("settings.showRegions", regionsRef.value.toString());
}
function toggleLanguages() {
  localStorage.setItem("settings.showLanguages", languagesRef.value.toString());
}
function toggleSiblings() {
  localStorage.setItem("settings.showSiblings", siblingsRef.value.toString());
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
            :class="groupRomsRef ? 'text-romm-accent-1' : ''"
            :icon="groupRomsRef ? 'mdi-group' : 'mdi-ungroup'"
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="groupRomsRef ? 'text-romm-accent-1' : ''"
              >Group roms</span
            >
            <p class="mt-1">
              Group versions of the same rom together in the gallery
            </p>
          </div>
        </v-col>
        <v-col cols="3" lg="2">
          <v-switch
            class="ml-3"
            v-model="groupRomsRef"
            color="romm-accent-1"
            @update:model-value="toggleGroupRoms"
            hide-details
          ></v-switch>
        </v-col>

        <v-col
          cols="8"
          lg="4"
          class="d-flex siblings-option"
          :class="{
            disabled: !groupRomsRef,
          }"
        >
          <v-icon
            :class="siblingsRef && groupRomsRef ? 'text-romm-accent-1' : ''"
            :icon="
              siblingsRef ? 'mdi-account-group-outline' : 'mdi-account-outline'
            "
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="siblingsRef && groupRomsRef ? 'text-romm-accent-1' : ''"
              >Show siblings</span
            >
            <p class="mt-1">
              Show siblings count in the gallery when "Group roms option is
              enabled"
            </p>
          </div>
        </v-col>
        <v-col cols="4" lg="2">
          <v-switch
            :disabled="!groupRomsRef"
            class="ml-3"
            v-model="siblingsRef"
            color="romm-accent-1"
            @update:model-value="toggleSiblings"
            hide-details
          ></v-switch>
        </v-col>
      </v-row>

      <v-row no-gutters class="align-center">
        <v-col cols="8" lg="4" class="d-flex">
          <v-icon
            :class="regionsRef ? 'text-romm-accent-1' : ''"
            :icon="
              regionsRef
                ? 'mdi-flag-variant-outline'
                : 'mdi-flag-variant-off-outline'
            "
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="regionsRef ? 'text-romm-accent-1' : ''"
              >Show regions</span
            >
            <p class="mt-1">Show region flags in the gallery</p>
          </div>
        </v-col>
        <v-col cols="4" lg="2">
          <v-switch
            class="ml-3"
            v-model="regionsRef"
            color="romm-accent-1"
            @update:model-value="toggleRegions"
            hide-details
          ></v-switch>
        </v-col>

        <v-col cols="8" lg="4" class="d-flex">
          <v-icon
            :class="languagesRef ? 'text-romm-accent-1' : ''"
            :icon="languagesRef ? 'mdi-flag-outline' : 'mdi-flag-off-outline'"
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="languagesRef ? 'text-romm-accent-1' : ''"
              >Show languages</span
            >
            <p class="mt-1">Show language flags in the gallery</p>
          </div>
        </v-col>
        <v-col cols="4" lg="2">
          <v-switch
            class="ml-3"
            v-model="languagesRef"
            color="romm-accent-1"
            @update:model-value="toggleLanguages"
            hide-details
          ></v-switch>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
<style scoped>
.siblings-option.disabled {
  opacity: 0.5;
}
</style>
