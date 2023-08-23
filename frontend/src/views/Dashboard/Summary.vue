<script setup>
import storePlatforms from "@/stores/platforms";

// Props
const platforms = storePlatforms();
</script>
<template>
  <v-card rounded="0">
    <v-card-text class="py-0 px-2">
      <v-chip-group>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-controller</v-icon
          >{{ platforms.value.length }} Platforms
        </v-chip>
        <v-chip class="text-overline" variant="text" label>
          <v-icon class="mr-2">mdi-disc</v-icon>{{ platforms.totalGames }} Games
        </v-chip>
      </v-chip-group>
    </v-card-text>
  </v-card>
</template>
