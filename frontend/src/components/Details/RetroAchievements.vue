<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import retroAchievementsApi from "@/services/api/retroAchivements";

import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import { ref } from "vue";
import { onBeforeMount } from "vue";

const emitter = inject<Emitter<Events>>("emitter");
const props = defineProps<{ rom: DetailedRom }>();
const retroAchievementsInfo = ref();

// Functions
async function fetchDetails() {
  await retroAchievementsApi
    .getGameInfo({ id: props.rom.ra_id as number })
    .then(({ data }) => {
      retroAchievementsInfo.value = data;
    })
    .catch((error) => {
      console.log(error);
    })
    .finally(() => {
      emitter?.emit("showLoadingDialog", { loading: false, scrim: false });
    });
}

onBeforeMount(async () => {
  emitter?.emit("showLoadingDialog", { loading: true, scrim: false });
  await fetchDetails();
});
</script>
<template>
  <div
    class="d-flex flex-column ga-2 flex-wrap mt-8"
    v-if="retroAchievementsInfo?.Achievements"
  >
    <h2>All awards</h2>
    <v-card
      v-for="achievement in Object.values(retroAchievementsInfo.Achievements)
        .sort((a) => {
          if (!a.DateEarned) return 1;
          return -1;
        })
        .sort(
          (a, b) =>
            (new Date(b.DateEarned) as any) - (new Date(a.DateEarned) as any),
        )"
      :key="achievement.ID"
      width="100%"
      class="d-flex pa-4"
    >
      <div class="d-flex align-center">
        <v-img
          class="flex-grow-0"
          :style="{ filter: `grayscale(${achievement.DateEarned ? 0 : 1})` }"
          height="64"
          width="64"
          :src="`https://media.retroachievements.org/Badge/${achievement.BadgeName}.png`"
        />
      </div>
      <div class="flex-grow-1">
        <v-card-title class="py-0"> {{ achievement.Title }}</v-card-title>
        <v-card-subtitle class="py-0">
          {{ achievement.Description }}</v-card-subtitle
        >

        <v-card-text class="py-0">
          <div
            v-if="achievement.DateEarned"
            class="text-caption text-medium-emphasis"
          >
            Completed on {{ achievement.DateEarned }}
          </div>
        </v-card-text>
      </div>
    </v-card>
  </div>
</template>
