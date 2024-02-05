<script setup lang="ts">
import type { EnhancedRomSchema } from "@/__generated__";
import { useDisplay } from "vuetify";

defineProps<{ rom: EnhancedRomSchema }>();
const { xs } = useDisplay();
</script>
<template>
  <template v-if="rom.genres.length > 0 || rom.franchises.length > 0 || rom.collections.length > 0 || rom.companies.length > 0">
    <v-divider class="mx-2 my-4" />
    <v-row v-if="rom.genres.length > 0" class="align-center my-3" no-gutters>
      <v-col cols="3" sm="3" md="2" xl="1">
        <span>Genres</span>
      </v-col>
      <v-col>
        <v-chip v-for="genre in rom.genres" class="my-1 mr-2" label>
          {{ genre.name }}
        </v-chip>
      </v-col>
    </v-row>
    <v-row v-if="rom.franchises.length > 0" class="align-center my-3" no-gutters>
      <v-col cols="3" sm="3" md="2" xl="1">
        <span>Franchises</span>
      </v-col>
      <v-col>
        <v-chip v-for="franchise in rom.franchises" class="my-1 mr-2" label>
          {{ franchise.name }}
        </v-chip>
      </v-col>
    </v-row>
    <v-row v-if="rom.collections.length > 0" class="align-center my-3" no-gutters>
      <v-col cols="3" sm="3" md="2" xl="1">
        <span>Collections</span>
      </v-col>
      <v-col>
        <v-chip v-for="collection in rom.collections" class="my-1 mr-2" label>
          {{ collection.name }}
        </v-chip>
      </v-col>
    </v-row>
    <v-row v-if="rom.companies.length > 0" class="align-center" no-gutters>
      <v-col cols="3" sm="3" md="2" xl="1">
        <span>Companies</span>
      </v-col>
      <v-col>
        <v-chip v-for="company in rom.companies" class="my-1 mr-2" label>
          {{ company.company.name }}
        </v-chip>
      </v-col>
    </v-row>
  </template>
  <template v-if="rom.summary != ''">
    <v-divider class="mx-2 my-4" />
    <v-row no-gutters>
      <v-col class="text-caption">
        <p>{{ rom.summary }}</p>
      </v-col>
    </v-row>
  </template>
  <template v-if="rom.merged_screenshots.length > 0">
    <v-divider class="mx-2 my-4" />
    <v-row no-gutters>
      <v-col>
        <v-carousel
          hide-delimiter-background
          delimiter-icon="mdi-square"
          class="bg-primary"
          show-arrows="hover"
          hide-delimiters
          progress="terciary"
          :height="xs ? '300' : '400'"
        >
          <template v-slot:prev="{ props }">
            <v-btn
              icon="mdi-chevron-left"
              class="translucent"
              @click="props.onClick"
            />
          </template>
          <v-carousel-item
            v-for="screenshot_url in rom.merged_screenshots"
            :src="screenshot_url"
          />
          <template v-slot:next="{ props }">
            <v-btn
              icon="mdi-chevron-right"
              class="translucent"
              @click="props.onClick"
            />
          </template>
        </v-carousel>
      </v-col>
    </v-row>
  </template>
</template>
