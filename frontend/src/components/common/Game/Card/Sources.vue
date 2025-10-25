<script setup lang="ts">
import type { SearchRom } from "@/stores/roms";

defineProps<{ rom: SearchRom }>();
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
        <v-avatar
          v-if="rom.igdb_id"
          class="mr-1 mb-1"
          v-bind="props"
          size="28"
          rounded="1"
        >
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
          class="mr-1 mb-1"
          size="28"
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
          class="mr-1 mb-1"
          size="28"
          rounded="1"
        >
          <v-img src="/assets/scrappers/ss.png" />
        </v-avatar>
      </template>
    </v-tooltip>
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      text="Launchbox matched"
      open-delay="500"
    >
      <template #activator="{ props }">
        <v-avatar
          v-bind="props"
          v-if="rom.launchbox_id"
          class="mr-1 mb-1"
          size="28"
          rounded="1"
        >
          <v-img src="/assets/scrappers/launchbox.png" />
        </v-avatar>
      </template>
    </v-tooltip>
    <v-tooltip
      location="top"
      class="tooltip"
      transition="fade-transition"
      text="Flashpoint matched"
      open-delay="500"
    >
      <template #activator="{ props }">
        <v-avatar
          v-bind="props"
          v-if="rom.flashpoint_id"
          class="mr-1 mb-1"
          size="28"
          rounded="1"
        >
          <v-img src="/assets/scrappers/flashpoint.png" />
        </v-avatar>
      </template>
    </v-tooltip>
  </v-row>
</template>
