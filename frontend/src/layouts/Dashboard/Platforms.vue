<script setup lang="ts">
import PlatformCard from "@/components/common/Platform/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storePlatforms from "@/stores/platforms";
import { views } from "@/utils";

// Props
const platforms = storePlatforms();
</script>
<template>
  <r-section icon="mdi-controller" title="Platforms">
    <template #content>
      <v-row no-gutters>
        <v-col
          v-for="platform in platforms.filledPlatforms"
          :key="platform.slug"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <platform-card :key="platform.slug" :platform="platform" />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
