<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { useI18n } from "vue-i18n";
import RSection from "@/components/common/RSection.vue";
import { views } from "@/utils";

const { t } = useI18n();
const gridPlatforms = useLocalStorage("settings.gridPlatforms", false);
const PLATFORM_SKELETON_COUNT = 12;
</script>

<template>
  <RSection icon="mdi-shimmer" :title="t('common.platforms')">
    <template #toolbar-append>
      <v-skeleton-loader type="button" />
    </template>
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridPlatforms }"
        class="py-1 overflow-y-hidden"
        no-gutters
      >
        <v-col
          v-for="index in PLATFORM_SKELETON_COUNT"
          :key="index"
          class="align-self-end pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <v-skeleton-loader
            class="platform-skeleton"
            type="heading, image"
            aspect-ratio="1.2"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>

<style>
.platform-skeleton .v-skeleton-loader__heading {
  margin: 8px;
  height: 20px;
}
</style>
