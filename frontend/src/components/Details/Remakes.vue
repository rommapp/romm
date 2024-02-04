<script setup lang="ts">
import type { Rom } from "@/stores/roms";

defineProps<{ rom: Rom }>();
</script>
<template>
    <v-row no-gutters>
      <v-col class="pa-0" cols="4" sm="2" md="3" lg="3" v-for="remake in rom.remakes">
        <v-card class="ma-1">
          <v-img
            class="cover"
            :src="`https:${remake.cover.url.replace('t_thumb', 't_cover_big')}`"
            :lazy-src="`https:${remake.cover.url.replace(
              't_thumb',
              't_cover_small'
            )}`"
            :aspect-ratio="3 / 4"
          />
        </v-card>
      </v-col>
    </v-row>
</template>
