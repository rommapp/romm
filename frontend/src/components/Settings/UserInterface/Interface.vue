<script setup lang="ts">
import InterfaceOption from "@/components/Settings/UserInterface/InterfaceOption.vue";
import RSection from "@/components/common/RSection.vue";
import { computed, ref } from "vue";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
// Initializing refs from localStorage
const storedShowRecentRoms = localStorage.getItem("settings.showRecentRoms");
const showRecentRomsRef = ref(
  isNull(storedShowRecentRoms) ? true : storedShowRecentRoms === "true",
);
const storedGridRecentRoms = localStorage.getItem("settings.gridRecentRoms");
const gridRecentRomsRef = ref(
  isNull(storedGridRecentRoms) ? false : storedGridRecentRoms === "true",
);
const storedShowContinuePlaying = localStorage.getItem(
  "settings.showContinuePlaying",
);
const showContinuePlayingRef = ref(
  isNull(storedShowContinuePlaying)
    ? true
    : storedShowContinuePlaying === "true",
);
const storedGridContinuePlaying = localStorage.getItem(
  "settings.gridContinuePlaying",
);
const gridContinuePlayingRef = ref(
  isNull(storedGridContinuePlaying)
    ? false
    : storedGridContinuePlaying === "true",
);
const storedShowPlatforms = localStorage.getItem("settings.showPlatforms");
const showPlatformsRef = ref(
  isNull(storedShowPlatforms) ? true : storedShowPlatforms === "true",
);
const storedGridPlatforms = localStorage.getItem("settings.gridPlatforms");
const gridPlatformsRef = ref(
  isNull(storedGridPlatforms) ? true : storedGridPlatforms === "true",
);
const storedShowCollections = localStorage.getItem("settings.showCollections");
const showCollectionsRef = ref(
  isNull(storedShowCollections) ? true : storedShowCollections === "true",
);
const storedGridCollections = localStorage.getItem("settings.gridCollections");
const gridCollectionsRef = ref(
  isNull(storedGridCollections) ? true : storedGridCollections === "true",
);

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

const homeOptions = computed(() => [
  {
    title: t("settings.show-recently-added"),
    description: t("settings.show-recently-added-desc"),
    iconEnabled: "mdi-shimmer",
    iconDisabled: "mdi-shimmer",
    model: showRecentRomsRef,
    modelTrigger: toggleShowRecentRoms,
  },
  {
    title: t("settings.recently-added-as-grid"),
    description: t("settings.recently-added-as-grid-desc"),
    iconEnabled: "mdi-view-comfy",
    iconDisabled: "mdi-view-column",
    disabled: !showRecentRomsRef.value,
    model: gridRecentRomsRef,
    modelTrigger: toggleGridRecentRoms,
  },
  {
    title: t("settings.show-continue-playing"),
    description: t("settings.show-continue-playing-desc"),
    iconEnabled: "mdi-play",
    iconDisabled: "mdi-play",
    model: showContinuePlayingRef,
    modelTrigger: toggleShowContinuePlaying,
  },
  {
    title: t("settings.continue-playing-as-grid"),
    description: t("settings.continue-playing-as-grid-desc"),
    iconEnabled: "mdi-view-comfy",
    iconDisabled: "mdi-view-column",
    disabled: !showContinuePlayingRef.value,
    model: gridContinuePlayingRef,
    modelTrigger: toggleGridContinuePlaying,
  },
  {
    title: t("settings.show-platforms"),
    description: t("settings.show-platforms-desc"),
    iconEnabled: "mdi-controller",
    iconDisabled: "mdi-controller",
    model: showPlatformsRef,
    modelTrigger: toggleShowPlatforms,
  },
  {
    title: t("settings.show-platforms-as-grid"),
    description: t("settings.show-platforms-as-grid-desc"),
    iconEnabled: "mdi-view-comfy",
    iconDisabled: "mdi-view-column",
    disabled: !showPlatformsRef.value,
    model: gridPlatformsRef,
    modelTrigger: toggleGridPlatforms,
  },
  {
    title: t("settings.show-collections"),
    description: t("settings.show-collections-desc"),
    iconEnabled: "mdi-bookmark-box-multiple",
    iconDisabled: "mdi-bookmark-box-multiple",
    model: showCollectionsRef,
    modelTrigger: toggleShowCollections,
  },
  {
    title: t("settings.show-collections-as-grid"),
    description: t("settings.show-collections-as-grid-desc"),
    iconEnabled: "mdi-view-comfy",
    iconDisabled: "mdi-view-column",
    disabled: !showCollectionsRef.value,
    model: gridCollectionsRef,
    modelTrigger: toggleGridCollections,
  },
]);

const galleryOptions = computed(() => [
  {
    title: t("settings.group-roms"),
    description: t("settings.group-roms-desc"),
    iconEnabled: "mdi-group",
    iconDisabled: "mdi-ungroup",
    model: groupRomsRef,
    modelTrigger: toggleGroupRoms,
  },
  {
    title: t("settings.show-siblings"),
    description: t("settings.show-siblings-desc"),
    iconEnabled: "mdi-account-group-outline",
    iconDisabled: "mdi-account-outline",
    model: siblingsRef,
    disabled: !groupRomsRef.value,
    modelTrigger: toggleSiblings,
  },
  {
    title: t("settings.show-regions"),
    description: t("settings.show-regions-desc"),
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: regionsRef,
    modelTrigger: toggleRegions,
  },
  {
    title: t("settings.show-languages"),
    description: t("settings.show-languages-desc"),
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: languagesRef,
    modelTrigger: toggleLanguages,
  },
  {
    title: t("settings.show-status"),
    description: t("settings.show-status-desc"),
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: statusRef,
    modelTrigger: toggleStatus,
  },
]);

// Functions to update localStorage
const toggleShowRecentRoms = (value: boolean) => {
  showRecentRomsRef.value = value;
  localStorage.setItem("settings.showRecentRoms", value.toString());
};
const toggleGridRecentRoms = (value: boolean) => {
  gridRecentRomsRef.value = value;
  localStorage.setItem("settings.gridRecentRoms", value.toString());
};
const toggleShowContinuePlaying = (value: boolean) => {
  showContinuePlayingRef.value = value;
  localStorage.setItem("settings.showContinuePlaying", value.toString());
};
const toggleGridContinuePlaying = (value: boolean) => {
  gridContinuePlayingRef.value = value;
  localStorage.setItem("settings.gridContinuePlaying", value.toString());
};
const toggleShowPlatforms = (value: boolean) => {
  showPlatformsRef.value = value;
  localStorage.setItem("settings.showPlatforms", value.toString());
};
const toggleGridPlatforms = (value: boolean) => {
  gridPlatformsRef.value = value;
  localStorage.setItem("settings.gridPlatforms", value.toString());
};
const toggleShowCollections = (value: boolean) => {
  showCollectionsRef.value = value;
  localStorage.setItem("settings.showCollections", value.toString());
};
const toggleGridCollections = (value: boolean) => {
  gridCollectionsRef.value = value;
  localStorage.setItem("settings.gridCollections", value.toString());
};

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
</script>
<template>
  <r-section icon="mdi-palette-swatch-outline" :title="t('settings.interface')">
    <template #content>
      <v-chip label variant="text" prepend-icon="mdi-home" class="ml-2">{{
        t("settings.home")
      }}</v-chip>
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
        >{{ t("settings.gallery") }}</v-chip
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
