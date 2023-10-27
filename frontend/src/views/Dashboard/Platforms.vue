<script setup>
import { views } from "@/utils/utils";
import PlatformCard from "@/components/Platform/PlatformCard.vue";
import storePlatforms from "@/stores/platforms";

// Props
const platforms = storePlatforms();
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact"
      ><v-toolbar-title class="text-button"
        ><v-icon class="mr-3">mdi-controller</v-icon>Platforms</v-toolbar-title
      ></v-toolbar
    >
    <v-divider class="border-opacity-25" />
    <v-card-text>
      <v-row>
        <v-col
          v-for="platform in platforms.value"
          class="pa-1"
          :key="platform.slug"
          :cols="views[0]['size-cols']"
          :xs="views[0]['size-xs']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
        >
          <platform-card :platform="platform" :key="platform.slug" />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>
