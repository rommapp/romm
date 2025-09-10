<script setup lang="ts">
import type { SearchRomSchema } from "@/__generated__";

defineProps<{ rom: SearchRomSchema }>();
</script>

<template>
  <v-row no-gutters class="text-white pa-1">
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      text="IGDB matched"
      open-delay="500"
    >
      <template #activator="{ props }">
        <v-avatar v-if="rom.igdb_id" v-bind="props" size="30" rounded="1">
          <v-img src="/assets/scrappers/igdb.png" />
        </v-avatar>
      </template>
    </v-tooltip>
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      text="Mobygames matched"
      open-delay="500"
    >
      <template #activator="{ props }">
        <v-avatar
          v-if="rom.moby_id"
          v-bind="props"
          class="ml-1"
          size="30"
          rounded="1"
        >
          <v-img src="/assets/scrappers/moby.png" />
        </v-avatar>
      </template>
    </v-tooltip>
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      text="Screenscraper matched"
      open-delay="500"
    >
      <template #activator="{ props }">
        <v-avatar
          v-if="rom.ss_id"
          v-bind="props"
          class="ml-1"
          size="30"
          rounded="1"
        >
          <v-img src="/assets/scrappers/ss.png" />
        </v-avatar>
      </template>
    </v-tooltip>
  </v-row>
</template>
