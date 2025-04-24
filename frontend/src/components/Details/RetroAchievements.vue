<script setup lang="ts">
import type { DetailedRom } from "@/stores/roms";
import storeAuth from "@/stores/auth";
import { ref, onMounted } from "vue";
import type { RAGameRomAchievement } from "@/__generated__/models/RAGameRomAchievement";

// Props
const props = defineProps<{ rom: DetailedRom }>();
const auth = storeAuth();
const targetRom = ref();
const earnedAchievements = ref<{ id: string; date: string }[]>([]);
const achievemehtsPercentage = ref(0);
const showEarned = ref(false);
const filteredAchievements = ref<RAGameRomAchievement[]>([]);

function toggleShowEarned() {
  showEarned.value = !showEarned.value;
  if (showEarned.value) {
    filteredAchievements.value = filteredAchievements.value.filter(
      (achievement) =>
        earnedAchievements.value.some(
          (earned) => earned.id === (achievement.badge_id ?? ""),
        ),
    );
  } else {
    filteredAchievements.value = (
      props.rom.merged_ra_metadata?.achievements ?? []
    ).sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  }
}

onMounted(() => {
  filteredAchievements.value = (
    props.rom.merged_ra_metadata?.achievements ?? []
  ).sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  if (auth.user?.ra_progression?.results) {
    targetRom.value = auth.user.ra_progression.results.find(
      (result) => result.rom_ra_id === props.rom.ra_id,
    );
    if (targetRom.value) {
      earnedAchievements.value = targetRom.value.earned_achievements.map(
        (achievement: { id: string; date: string }) => ({
          id: achievement.id,
          date: achievement.date,
        }),
      );
      if (props.rom.merged_ra_metadata?.achievements) {
        achievemehtsPercentage.value = Math.round(
          (targetRom.value.earned_achievements.length /
            props.rom.merged_ra_metadata?.achievements.length) *
            100,
        );
      }
    }
  }
});
</script>
<template>
  <v-list-item>
    <template #prepend>
      <span
        v-if="targetRom && rom.merged_ra_metadata?.achievements"
        class="mr-4"
        >{{ targetRom.earned_achievements.length }} /
        {{ rom.merged_ra_metadata?.achievements.length }}</span
      >
    </template>
    <v-progress-linear
      color="accent"
      :model-value="achievemehtsPercentage"
      class="my-4"
      height="20"
      rounded
      ><p>{{ Math.ceil(achievemehtsPercentage) }}%</p></v-progress-linear
    >
  </v-list-item>
  <v-chip
    :color="showEarned ? 'primary' : 'gray'"
    @click="toggleShowEarned"
    class="my-2"
    ><template #prepend
      ><v-icon class="mr-2">{{
        showEarned ? "mdi-checkbox-outline" : "mdi-checkbox-blank-outline"
      }}</v-icon></template
    >Show earned only</v-chip
  >
  <v-list v-if="rom.merged_ra_metadata?.achievements" class="bg-background">
    <v-list-item
      v-for="achievement in filteredAchievements"
      :title="achievement.title?.toString()"
      :subtitle="achievement.description?.toString()"
      class="mb-2 py-4 rounded bg-toplayer"
      :class="{
        earned: earnedAchievements.some(
          (earned) => earned.id === (achievement.badge_id ?? ''),
        ),
        hidden:
          showEarned &&
          !earnedAchievements.some(
            (earned) => earned.id === (achievement.badge_id ?? ''),
          ),
      }"
    >
      <template #prepend>
        <v-avatar
          v-if="achievement.badge_path_lock || achievement.badge_path"
          rounded="0"
        >
          <v-img
            :src="
              earnedAchievements.some(
                (earned) => earned.id === (achievement.badge_id ?? ''),
              )
                ? (achievement.badge_path ?? '')
                : (achievement.badge_path_lock ?? '')
            "
          />
        </v-avatar>
      </template>
      <template #append>
        <v-chip
          label
          size="small"
          v-if="
            earnedAchievements.some(
              (earned) => earned.id === (achievement.badge_id ?? ''),
            )
          "
        >
          {{
            earnedAchievements.find(
              (earned) => earned.id === (achievement.badge_id ?? ""),
            )?.date
          }}
        </v-chip>
      </template>
    </v-list-item>
  </v-list>
</template>

<style scoped>
.earned {
  border-left: solid rgba(var(--v-theme-primary)) 4px;
}
.hidden {
  display: none;
}
</style>
