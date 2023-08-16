<script setup>
import storePlatforms from "@/stores/platforms.js";
const platforms = storePlatforms();
const totalGames = platforms.totalGames;
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-text-box-outline</v-icon
        >Summary</v-toolbar-title
      >
    </v-toolbar>
    <v-divider class="border-opacity-25" />
    <v-card-text>
      <v-chip-group>
        <v-chip class="text-overline bg-chip" label>
          <v-icon class="mr-2">mdi-controller</v-icon
          >{{ platforms.value.length }} Platforms
        </v-chip>
        <v-chip class="text-overline bg-chip" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ totalGames }} Games
        </v-chip>
      </v-chip-group>
    </v-card-text>
  </v-card>
</template>
