<script setup lang="ts">
import { isUndefined } from "lodash";
import { ref } from "vue";

const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRoms = ref(
  isUndefined(storedGroupRoms) ? true : storedGroupRoms === "true"
);
const storedRegions = localStorage.getItem("settings.showRegions");
const regions = ref(
  isUndefined(storedRegions) ? true : storedRegions === "true"
);
const storedLanguages = localStorage.getItem("settings.showLanguages");
const languages = ref(
  isUndefined(storedLanguages) ? true : storedLanguages === "true"
);
const storedSiblings = localStorage.getItem("settings.showSiblings");
const siblings = ref(
  isUndefined(storedSiblings) ? true : storedSiblings === "true"
);

// Functions
function toggleGroupRoms() {
  localStorage.setItem("settings.groupRoms", groupRoms.value.toString());
}
function toggleRegions() {
  localStorage.setItem("settings.showRegions", regions.value.toString());
}
function toggleLanguages() {
  localStorage.setItem("settings.showLanguages", languages.value.toString());
}
function toggleSiblings() {
  localStorage.setItem("settings.showSiblings", siblings.value.toString());
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
        <v-col cols="3" lg="2">
          <v-switch
            class="ml-3"
            v-model="groupRoms"
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
            disabled: !groupRoms,
          }"
        >
          <v-icon
            :class="siblings && groupRoms ? 'text-romm-accent-1' : ''"
            :icon="
              siblings
                ? 'mdi-account-group-outline'
                : 'mdi-account-outline'
            "
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="siblings && groupRoms ? 'text-romm-accent-1' : ''"
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
            :disabled="!groupRoms"
            class="ml-3"
            v-model="siblings"
            color="romm-accent-1"
            @update:model-value="toggleSiblings"
            hide-details
          ></v-switch>
        </v-col>
      </v-row>

      <v-row no-gutters class="align-center">
        <v-col cols="8" lg="4" class="d-flex">
          <v-icon
            :class="regions ? 'text-romm-accent-1' : ''"
            :icon="
              regions
                ? 'mdi-flag-variant-outline'
                : 'mdi-flag-variant-off-outline'
            "
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="regions ? 'text-romm-accent-1' : ''"
              >Show regions</span
            >
            <p class="mt-1">Show region flags in the gallery</p>
          </div>
        </v-col>
        <v-col cols="4" lg="2">
          <v-switch
            class="ml-3"
            v-model="regions"
            color="romm-accent-1"
            @update:model-value="toggleRegions"
            hide-details
          ></v-switch>
        </v-col>

        <v-col cols="8" lg="4" class="d-flex">
          <v-icon
            :class="languages ? 'text-romm-accent-1' : ''"
            :icon="languages ? 'mdi-flag-outline' : 'mdi-flag-off-outline'"
          />
          <div class="ml-3">
            <span
              class="font-weight-bold text-body-1"
              :class="languages ? 'text-romm-accent-1' : ''"
              >Show languages</span
            >
            <p class="mt-1">Show language flags in the gallery</p>
          </div>
        </v-col>
        <v-col cols="4" lg="2">
          <v-switch
            class="ml-3"
            v-model="languages"
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
