<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import {
  buildAuthorization,
  getGameInfoAndUserProgress,
} from "@retroachievements/api";
import storeAuth from "@/stores/auth";
const props = defineProps<{ rom: DetailedRom }>();
const auth = storeAuth();

const authorization = buildAuthorization({
  username: auth.user?.ra_username as string,
  webApiKey: auth.user?.ra_api_key as string,
});

// Then, make the API call.
const gameExtended = await getGameInfoAndUserProgress(authorization, {
  gameId: props.rom.ra_id as number,
  username: auth.user?.ra_username as string,
  shouldIncludeHighestAwardMetadata: true,
});
</script>
<template>
  <div class="d-flex flex-column ga-2 flex-wrap mt-8">
    <h2>All awards</h2>
    <v-card
      v-for="achievement in Object.values(gameExtended.achievements)
        .sort((a) => {
          if (!a.dateEarned) return 1;
          return -1;
        })
        .sort(
          (a, b) =>
            (new Date(b.dateEarned) as any) - (new Date(a.dateEarned) as any),
        )"
      :key="achievement.id"
      width="100%"
      class="d-flex pa-4"
    >
      <div class="d-flex align-center">
        <v-img
          class="flex-grow-0"
          :style="{ filter: `grayscale(${achievement.dateEarned ? 0 : 1})` }"
          height="64"
          width="64"
          :src="`https://media.retroachievements.org/Badge/${achievement.badgeName}.png`"
        />
      </div>
      <div class="flex-grow-1">
        <v-card-title class="py-0"> {{ achievement.title }}</v-card-title>
        <v-card-subtitle class="py-0">
          {{ achievement.description }}</v-card-subtitle
        >

        <v-card-text class="py-0">
          <div
            v-if="achievement.dateEarned"
            class="text-caption text-medium-emphasis"
          >
            Completed on {{ achievement.dateEarned }}
          </div>
        </v-card-text>
      </div>
    </v-card>
  </div>
</template>
