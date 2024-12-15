<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import retroAchievementsApi from "@/services/api/retroAchivements";
import type { RetroAchievementsGameSchema } from "@/__generated__";

import { inject } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import { ref } from "vue";
import { onBeforeMount } from "vue";

const emitter = inject<Emitter<Events>>("emitter");
const props = defineProps<{ rom: DetailedRom }>();
const retroAchievementsInfo = ref<RetroAchievementsGameSchema>();

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
    v-if="retroAchievementsInfo?.Achievements"
    class="d-flex flex-column ga-2 flex-wrap mt-8"
  >
    <v-row no-gutters>
      <v-col cols="12" sm="3">
        <v-sheet class="pa-2" width="100%">
          <b>Awards:</b> {{ retroAchievementsInfo.NumAwardedToUser }}/{{
            retroAchievementsInfo.NumAchievements
          }}
        </v-sheet>
      </v-col>
      <v-col cols="12" sm="3">
        <v-sheet class="pa-2" width="100%">
          <b>Completed:</b> {{ retroAchievementsInfo.UserCompletion }}
        </v-sheet>
      </v-col>
      <v-col cols="12" sm="3">
        <v-sheet class="pa-2" width="100%">
          <a
            target="_blank"
            :href="`https://retroachievements.org/game/${retroAchievementsInfo.ID}`"
          >
            Info</a
          >
        </v-sheet>
      </v-col>
      <v-col cols="12" sm="3">
        <v-sheet class="pa-2" width="100%">
          <a
            v-if="retroAchievementsInfo.GuideURL"
            :href="retroAchievementsInfo.GuideURL"
            target="_blank"
          >
            Guide</a
          >
        </v-sheet>
      </v-col>
    </v-row>

    <h2>All awards</h2>
    <v-card
      v-for="achievement in Object.values(retroAchievementsInfo.Achievements)
        .sort((a) => {
          if (!a.DateEarned) return 1;
          return -1;
        })
        .sort(
          (a, b) =>
            (new Date(b.DateEarned as string) as any) -
            (new Date(a.DateEarned as string) as any),
        )"
      :key="achievement.ID"
      width="100%"
      class="d-flex pa-4"
      :href="`https://retroachievements.org/achievement/${achievement.ID}`"
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
        <v-card-title
          class="py-0"
          style="word-wrap: break-word; white-space: normal"
        >
          {{ achievement.Title }}</v-card-title
        >
        <v-card-subtitle
          class="py-0"
          style="word-wrap: break-word; white-space: normal"
        >
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
