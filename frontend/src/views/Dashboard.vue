<script setup>
import { useDisplay } from "vuetify";
import { views } from "@/utils/utils.js";
import storePlatforms from "@/stores/platforms.js";
import PlatformCard from "@/components/Platform/PlatformCard.vue";

// Props
const platforms = storePlatforms();
const totalGames = platforms.totalGames;
const { lgAndUp } = useDisplay();
</script>

<template>
  <!-- Summary -->
  <v-row class="pa-1" no-gutters>
    <v-col>
      <v-card rounded="0">
        <v-card-title
          ><v-icon class="mr-2">mdi-text-box-outline</v-icon
          >Summary</v-card-title
        >
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
    </v-col>
  </v-row>

  <!-- Platforms -->
  <template v-if="platforms.value.length > 0">
    <v-row class="pa-1" no-gutters>
      <v-col>
        <v-card rounded="0">
          <v-card-title
            ><v-icon class="mr-2">mdi-controller</v-icon>Platforms</v-card-title
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
      </v-col>
    </v-row>
  </template>
</template>
