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
</script>
<template>
  <v-list v-if="rom.ra_metadata?.achievements" class="bg-background">
    <v-list-item
      v-for="achievement in rom.ra_metadata?.achievements.sort(
        (a, b) => (a.display_order ?? 0) - (b.display_order ?? 0),
      )"
      :title="achievement.title?.toString()"
      :subtitle="achievement.description?.toString()"
      class="mb-2 py-4 rounded bg-toplayer"
    >
      <template #prepend>
        <v-avatar rounded="0">
          <v-img
            :src="`https://media.retroachievements.org/Badge/${achievement.badge_id}_lock.png`"
          />
        </v-avatar>
      </template>
    </v-list-item>
  </v-list>
</template>
