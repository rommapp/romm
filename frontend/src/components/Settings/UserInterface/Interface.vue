<script setup lang="ts">
import InterfaceOption from "@/components/Settings/UserInterface/InterfaceOption.vue";
import RSection from "@/components/common/RSection.vue";
import { computed, ref } from "vue";
import { isNull } from "lodash";

// Initializing refs from localStorage
const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRomsRef = ref(
  isNull(storedGroupRoms) ? true : storedGroupRoms === "true",
);
const storedSiblings = localStorage.getItem("settings.showSiblings");
const siblingsRef = ref(
  isNull(storedSiblings) ? true : storedSiblings === "true",
);
const storedRegions = localStorage.getItem("settings.showRegions");
const regionsRef = ref(isNull(storedRegions) ? true : storedRegions === "true");
const storedLanguages = localStorage.getItem("settings.showLanguages");
const languagesRef = ref(
  isNull(storedLanguages) ? true : storedLanguages === "true",
);
const storedStatus = localStorage.getItem("settings.showStatus");
const statusRef = ref(isNull(storedStatus) ? true : storedStatus === "true");

const storedWrapRecentRoms = localStorage.getItem("settings.wrapRecentRoms");
const wrapRecentRomsRef = ref(
  isNull(storedWrapRecentRoms) ? true : storedWrapRecentRoms === "true",
);

const storedWrapPlatforms = localStorage.getItem("settings.wrapPlatforms");
const wrapPlatformsRef = ref(
  isNull(storedWrapPlatforms) ? true : storedWrapPlatforms === "true",
);
const storedWrapCollections = localStorage.getItem("settings.wrapCollections");
const wrapCollectionsRef = ref(
  isNull(storedWrapCollections) ? true : storedWrapCollections === "true",
);

const homeOptions = computed(() => [
  {
    title: "Wrap recent added roms",
    description: "Wrap recent added rom cards as a grid in the home page",
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: wrapRecentRomsRef,
    modelTrigger: toggleWrapRecentRoms,
  },
  {
    title: "Wrap platforms",
    description: "Wrap platform cards as a grid in the home page",
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: wrapPlatformsRef,
    modelTrigger: toggleWrapPlatforms,
  },
  {
    title: "Wrap collections",
    description: "Wrap collection cards as a grid in the home page",
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: wrapCollectionsRef,
    modelTrigger: toggleWrapCollections,
  },
]);

const galleryOptions = computed(() => [
  {
    title: "Group roms",
    description: "Group versions of the same rom together in the gallery",
    iconEnabled: "mdi-group",
    iconDisabled: "mdi-ungroup",
    model: groupRomsRef,
    modelTrigger: toggleGroupRoms,
  },
  {
    title: "Show siblings",
    description:
      'Show siblings count in the gallery when "Group roms" option is enabled',
    iconEnabled: "mdi-account-group-outline",
    iconDisabled: "mdi-account-outline",
    model: siblingsRef,
    disabled: !groupRomsRef.value,
    modelTrigger: toggleSiblings,
  },
  {
    title: "Show regions",
    description: "Show region flags in the gallery",
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: regionsRef,
    modelTrigger: toggleRegions,
  },
  {
    title: "Show languages",
    description: "Show language flags in the gallery",
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: languagesRef,
    modelTrigger: toggleLanguages,
  },
  {
    title: "Show status",
    description:
      "Show status icons in the gallery (backlogged, playing, completed, etc)",
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: statusRef,
    modelTrigger: toggleStatus,
  },
]);

// Functions to update localStorage
const toggleGroupRoms = (value: boolean) => {
  groupRomsRef.value = value;
  localStorage.setItem("settings.groupRoms", value.toString());
};

const toggleSiblings = (value: boolean) => {
  siblingsRef.value = value;
  localStorage.setItem("settings.showSiblings", value.toString());
};

const toggleRegions = (value: boolean) => {
  regionsRef.value = value;
  localStorage.setItem("settings.showRegions", value.toString());
};

const toggleLanguages = (value: boolean) => {
  languagesRef.value = value;
  localStorage.setItem("settings.showLanguages", value.toString());
};

const toggleStatus = (value: boolean) => {
  statusRef.value = value;
  localStorage.setItem("settings.showStatus", value.toString());
};
const toggleWrapRecentRoms = (value: boolean) => {
  wrapRecentRomsRef.value = value;
  localStorage.setItem("settings.wrapRecentRoms", value.toString());
};
const toggleWrapPlatforms = (value: boolean) => {
  wrapPlatformsRef.value = value;
  localStorage.setItem("settings.wrapPlatforms", value.toString());
};

const toggleWrapCollections = (value: boolean) => {
  wrapCollectionsRef.value = value;
  localStorage.setItem("settings.wrapCollections", value.toString());
};
</script>
<template>
  <r-section icon="mdi-palette-swatch-outline" title="Interface">
    <template #content>
      <v-chip label variant="text" prepend-icon="mdi-home" class="ml-2"
        >Home</v-chip
      >
      <v-divider class="border-opacity-25 mx-2" />
      <v-row class="py-1" no-gutters>
        <v-col
          cols="12"
          md="6"
          v-for="option in homeOptions"
          :key="option.title"
        >
          <interface-option
            class="mx-2"
            :disabled="option.disabled"
            :title="option.title"
            :description="option.description"
            :icon="
              option.model.value ? option.iconEnabled : option.iconDisabled
            "
            v-model="option.model.value"
            @update:model-value="option.modelTrigger"
          />
        </v-col>
      </v-row>
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-view-grid"
        class="ml-2 mt-4"
        >Gallery</v-chip
      >
      <v-divider class="border-opacity-25 mx-2" />
      <v-row class="py-1" no-gutters>
        <v-col
          cols="12"
          md="6"
          v-for="option in galleryOptions"
          :key="option.title"
        >
          <interface-option
            class="mx-2"
            :disabled="option.disabled"
            :title="option.title"
            :description="option.description"
            :icon="
              option.model.value ? option.iconEnabled : option.iconDisabled
            "
            v-model="option.model.value"
            @update:model-value="option.modelTrigger"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
