<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import InterfaceOption from "@/components/Settings/UserInterface/InterfaceOption.vue";
import RSection from "@/components/common/RSection.vue";
import { useUISettings } from "@/composables/useUISettings";
import storeCollections from "@/stores/collections";

const { t } = useI18n();
const { smAndDown } = useDisplay();
const collectionsStore = storeCollections();

// Get UI settings from the composable
const {
  showStats: showStatsRef,
  showRecentRoms: showRecentRomsRef,
  showContinuePlaying: showContinuePlayingRef,
  showPlatforms: showPlatformsRef,
  showCollections: showCollectionsRef,
  showVirtualCollections: showVirtualCollectionsRef,
  virtualCollectionType: virtualCollectionTypeRef,
  platformsGroupBy: platformsGroupByRef,
  groupRoms: groupRomsRef,
  showSiblings: siblingsRef,
  showRegions: regionsRef,
  showLanguages: languagesRef,
  showStatus: statusRef,
  showActionBar: actionBarRef,
  showGameTitle: gameTitleRef,
  enable3DEffect: enable3DEffectRef,
  enableExperimentalCache: enableExperimentalCacheRef,
  disableAnimations: disableAnimationsRef,
  boxartStyle: boxartStyleRef,
} = useUISettings();

// Boxart
export type BoxartStyleOption =
  | "cover_path"
  | "box3d_path"
  | "physical_path"
  | "miximage_path";

const homeOptions = computed(() => [
  {
    title: t("settings.show-stats"),
    description: t("settings.show-stats-desc"),
    iconEnabled: "mdi-thermostat-box",
    iconDisabled: "mdi-thermostat-box",
    model: showStatsRef,
    modelTrigger: toggleShowStats,
  },
  {
    title: t("settings.show-recently-added"),
    description: t("settings.show-recently-added-desc"),
    iconEnabled: "mdi-shimmer",
    iconDisabled: "mdi-shimmer",
    model: showRecentRomsRef,
    modelTrigger: toggleShowRecentRoms,
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
    title: t("settings.show-platforms"),
    description: t("settings.show-platforms-desc"),
    iconEnabled: "mdi-controller",
    iconDisabled: "mdi-controller",
    model: showPlatformsRef,
    modelTrigger: toggleShowPlatforms,
  },
  {
    title: t("settings.show-collections"),
    description: t("settings.show-collections-desc"),
    iconEnabled: "mdi-bookmark-box-multiple",
    iconDisabled: "mdi-bookmark-box-multiple",
    model: showCollectionsRef,
    modelTrigger: toggleShowCollections,
  },
]);

const platformsDrawerOptions = computed(() => [
  {
    title: t("settings.group-platforms-by"),
    description: t("settings.group-platforms-by-desc"),
    iconEnabled: "mdi-controller",
    iconDisabled: "mdi-controller",
    model: platformsGroupByRef,
    modelTrigger: setPlatformDrawerGroupBy,
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
    disabled: !groupRomsRef,
    modelTrigger: toggleSiblings,
  },
  {
    title: t("settings.show-game-titles"),
    description: t("settings.show-game-titles-desc"),
    iconEnabled: "mdi-subtitles",
    iconDisabled: "mdi-subtitles-outline",
    model: gameTitleRef,
    modelTrigger: toggleShowGameTitles,
  },
  {
    title: t("settings.show-actionbar"),
    description: t("settings.show-actionbar-desc"),
    iconEnabled: "mdi-card",
    iconDisabled: "mdi-card-outline",
    model: actionBarRef,
    modelTrigger: toggleActionBar,
  },
  {
    title: t("settings.show-status"),
    description: t("settings.show-status-desc"),
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: statusRef,
    modelTrigger: toggleStatus,
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
    title: t("settings.enable-3d-effect"),
    description: t("settings.enable-3d-effect-desc"),
    iconEnabled: "mdi-cube",
    iconDisabled: "mdi-cube-outline",
    model: enable3DEffectRef,
    modelTrigger: toggle3DEffect,
  },
  {
    title: t("settings.disable-animations"),
    description: t("settings.disable-animations-desc"),
    iconEnabled: "mdi-motion-pause",
    iconDisabled: "mdi-motion-play",
    model: disableAnimationsRef,
    modelTrigger: toggleDisableAnimations,
  },
  {
    title: t("settings.enable-experimental-cache"),
    description: t("settings.enable-experimental-cache-desc"),
    iconEnabled: "mdi-cached",
    iconDisabled: "mdi-cached",
    model: enableExperimentalCacheRef,
    modelTrigger: toggleExperimentalCache,
  },
]);

const boxartStyleOptions = computed(() => [
  { title: t("settings.boxart-cover"), value: "cover_path" },
  { title: t("settings.boxart-box3d"), value: "box3d_path" },
  { title: t("settings.boxart-physical"), value: "physical_path" },
  { title: t("settings.boxart-miximage"), value: "miximage_path" },
]);

const setPlatformDrawerGroupBy = (value: string | null) => {
  platformsGroupByRef.value = value;
};
const toggleShowContinuePlaying = (value: boolean) => {
  showContinuePlayingRef.value = value;
};
const toggleShowPlatforms = (value: boolean) => {
  showPlatformsRef.value = value;
};
const toggleShowCollections = (value: boolean) => {
  showCollectionsRef.value = value;
};
const toggleShowVirtualCollections = (value: boolean) => {
  showVirtualCollectionsRef.value = value;
};
const setVirtualCollectionType = async (value: string) => {
  virtualCollectionTypeRef.value = value;
  collectionsStore.fetchVirtualCollections(value);
};
const setBoxartStyle = (value: string) => {
  boxartStyleRef.value = value as BoxartStyleOption;
};
const toggleShowStats = (value: boolean) => {
  showStatsRef.value = value;
};
const toggleShowRecentRoms = (value: boolean) => {
  showRecentRomsRef.value = value;
};
const toggleGroupRoms = (value: boolean) => {
  groupRomsRef.value = value;
};
const toggleSiblings = (value: boolean) => {
  siblingsRef.value = value;
};

const toggleRegions = (value: boolean) => {
  regionsRef.value = value;
};
const toggleLanguages = (value: boolean) => {
  languagesRef.value = value;
};
const toggleStatus = (value: boolean) => {
  statusRef.value = value;
};
const toggleActionBar = (value: boolean) => {
  actionBarRef.value = value;
};
const toggle3DEffect = (value: boolean) => {
  enable3DEffectRef.value = value;
};
const toggleShowGameTitles = (value: boolean) => {
  gameTitleRef.value = value;
};
const toggleExperimentalCache = (value: boolean) => {
  enableExperimentalCacheRef.value = value;
};
const toggleDisableAnimations = (value: boolean) => {
  disableAnimationsRef.value = value;
};
</script>
<template>
  <RSection
    icon="mdi-palette-swatch-outline"
    :title="t('settings.interface')"
    class="ma-2"
  >
    <template #content>
      <v-chip label variant="text" prepend-icon="mdi-home" class="ml-2 mt-1">
        {{ t("settings.home") }}
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row class="py-1" no-gutters>
        <v-col
          v-for="option in homeOptions"
          :key="option.title"
          cols="12"
          md="6"
        >
          <InterfaceOption
            v-model="option.model.value"
            class="ma-1"
            :title="option.title"
            :description="option.description"
            :icon="
              option.model.value ? option.iconEnabled : option.iconDisabled
            "
            @update:model-value="option.modelTrigger"
          />
        </v-col>
      </v-row>
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-controller"
        class="ml-2 mt-4"
      >
        {{ t("settings.platforms-drawer") }}
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row class="align-center py-1" no-gutters>
        <v-col
          v-for="option in platformsDrawerOptions"
          :key="option.title"
          cols="12"
          md="6"
        >
          <v-select
            v-model="platformsGroupByRef"
            :items="[
              { title: 'Manufacturer', value: 'family_name' },
              { title: 'Generation', value: 'generation' },
              { title: 'Type', value: 'category' },
              { title: 'None', value: null },
            ]"
            :label="t('settings.platforms-drawer-group-by')"
            class="mx-2 mt-2"
            variant="outlined"
            hide-details
            @update:model-value="setPlatformDrawerGroupBy"
          />
        </v-col>
      </v-row>
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-view-grid"
        class="ml-2 mt-4"
      >
        {{ t("settings.gallery") }}
      </v-chip>
      <v-divider class="border-opacity-25 ma-1" />
      <v-row class="py-1" no-gutters>
        <v-col
          v-for="option in galleryOptions"
          :key="option.title"
          cols="12"
          md="6"
        >
          <InterfaceOption
            v-model="option.model.value"
            class="ma-1"
            :disabled="option.disabled"
            :title="option.title"
            :description="option.description"
            :icon="
              option.model.value ? option.iconEnabled : option.iconDisabled
            "
            @update:model-value="option.modelTrigger"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-select
            v-model="boxartStyleRef"
            :items="boxartStyleOptions"
            :label="t('settings.boxart-style')"
            class="mx-2 mt-2"
            variant="outlined"
            hide-details
            @update:model-value="setBoxartStyle"
          />
        </v-col>
      </v-row>
      <v-chip
        label
        variant="text"
        prepend-icon="mdi-view-grid"
        class="ml-2 mt-4"
      >
        {{ t("common.virtual-collections") }}
      </v-chip>
      <v-divider class="border-opacity-25 mx-2 mb-2" />
      <v-row class="py-1 align-center" no-gutters>
        <v-col cols="12" md="6">
          <InterfaceOption
            v-model="showVirtualCollectionsRef"
            class="mx-2"
            :title="t('settings.show-virtual-collections')"
            :description="t('settings.show-virtual-collections-desc')"
            :icon="
              showVirtualCollectionsRef
                ? 'mdi-bookmark-box-multiple'
                : 'mdi-bookmark-box-multiple'
            "
            @update:model-value="toggleShowVirtualCollections"
          />
        </v-col>
        <v-col cols="12" md="6">
          <v-select
            v-model="virtualCollectionTypeRef"
            :items="[
              { title: 'IGDB Collection', value: 'collection' },
              { title: 'Franchise', value: 'franchise' },
              { title: 'Genre', value: 'genre' },
              { title: 'Play Mode', value: 'mode' },
              { title: 'Developer', value: 'company' },
              { title: 'All (slow)', value: 'all' },
            ]"
            :label="t('settings.virtual-collection-type')"
            class="mx-2"
            :class="{ 'mt-4': smAndDown }"
            variant="outlined"
            hide-details
            :disabled="!showVirtualCollectionsRef"
            @update:model-value="setVirtualCollectionType"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
