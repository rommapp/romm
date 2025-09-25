<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import type { EarnedAchievement } from "@/__generated__/models/EarnedAchievement";
import type { RAGameRomAchievement } from "@/__generated__/models/RAGameRomAchievement";
import type { RAUserGameProgression } from "@/__generated__/models/RAUserGameProgression";
import storeAuth from "@/stores/auth";
import type { DetailedRom } from "@/stores/roms";

const { smAndDown } = useDisplay();
const props = defineProps<{ rom: DetailedRom }>();
const { t } = useI18n();
const auth = storeAuth();
const raUserAchivement = ref<RAUserGameProgression | undefined>();
const earnedAchievements = ref<EarnedAchievement[]>([]);
const achievementsPercentage = ref(0);
const achievementsPercentageHardcore = ref(0);
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

const isAchievementEarned = computed(
  () => (achievement: RAGameRomAchievement) => {
    return earnedAchievements.value.some(
      (earned) => earned.id === (achievement.badge_id ?? ""),
    );
  },
);

const isAchievementEarnedHarcore = computed(
  () => (achievement: RAGameRomAchievement) => {
    return earnedAchievements.value.some(
      (earned) =>
        achievement.badge_id &&
        earned.id === achievement.badge_id &&
        earned.date_hardcore,
    );
  },
);

const getAchievementEarnedDate = computed(
  () => (achievement: RAGameRomAchievement) => {
    return earnedAchievements.value.find(
      (earned) => earned.id === (achievement.badge_id ?? ""),
    )?.date;
  },
);

onMounted(() => {
  filteredAchievements.value = (
    props.rom.merged_ra_metadata?.achievements ?? []
  ).sort((a, b) => (a.display_order ?? 0) - (b.display_order ?? 0));
  if (auth.user?.ra_progression?.results) {
    raUserAchivement.value = auth.user.ra_progression.results.find(
      (result) => result.rom_ra_id === props.rom.ra_id,
    );
    if (raUserAchivement.value) {
      earnedAchievements.value = raUserAchivement.value.earned_achievements.map(
        (achievement) => ({
          ...achievement,
          date: achievement.date_hardcore || achievement.date,
        }),
      );
      if (props.rom.merged_ra_metadata?.achievements) {
        achievementsPercentage.value = Math.round(
          (raUserAchivement.value.earned_achievements.length /
            props.rom.merged_ra_metadata?.achievements.length) *
            100,
        );
        achievementsPercentageHardcore.value = Math.round(
          (raUserAchivement.value.earned_achievements.filter(
            (achievement: { date_hardcore?: string }) =>
              achievement.date_hardcore,
          ).length /
            props.rom.merged_ra_metadata?.achievements.length) *
            100,
        );
      }
    }
  }
});
</script>
<template>
  <v-list-item class="pa-0 mt-2">
    <template #prepend>
      <v-chip v-if="rom.merged_ra_metadata?.achievements" label rounded="0">
        <v-icon class="mr-2"> mdi-trophy </v-icon
        >{{ raUserAchivement?.earned_achievements.length ?? 0 }} /
        {{ rom.merged_ra_metadata?.achievements.length }}
      </v-chip>
    </template>
    <v-progress-linear
      bg-color="secondary"
      color="romm-gold"
      :model-value="achievementsPercentageHardcore"
      buffer-color="primary"
      buffer-opacity="0.6"
      :buffer-value="achievementsPercentage"
      height="32"
    >
      <p class="text-shadow">
        {{
          Math.max(
            Math.ceil(achievementsPercentage),
            Math.ceil(achievementsPercentageHardcore),
          )
        }}%
      </p>
    </v-progress-linear>
  </v-list-item>
  <v-chip
    label
    :color="showEarned ? 'primary' : 'gray'"
    class="mt-4"
    @click="toggleShowEarned"
  >
    <template #prepend>
      <v-icon class="mr-2">
        {{ showEarned ? "mdi-checkbox-outline" : "mdi-checkbox-blank-outline" }}
      </v-icon>
    </template>
    {{ t("rom.show-earned-only") }}
  </v-chip>
  <v-list v-if="rom.merged_ra_metadata?.achievements" class="bg-background">
    <v-list-item
      v-for="achievement in filteredAchievements"
      :key="achievement.ra_id || ''"
      :title="achievement.title?.toString()"
      class="mb-2 py-4 rounded bg-toplayer"
      :class="{
        earned:
          isAchievementEarned(achievement) &&
          !isAchievementEarnedHarcore(achievement),
        'earned-hardcore': isAchievementEarnedHarcore(achievement),
        locked: !isAchievementEarned(achievement),
        hidden: showEarned && !isAchievementEarned(achievement),
      }"
    >
      <template #prepend>
        <v-avatar
          v-if="achievement.badge_path_lock || achievement.badge_path"
          rounded="0"
        >
          <a
            :href="`https://retroachievements.org/achievement/${achievement.ra_id}`"
            target="_blank"
            class="h-100 w-100"
            :aria-label="achievement.badge_id || 'Achievement badge'"
          >
            <v-img
              :src="
                isAchievementEarned(achievement)
                  ? (achievement.badge_path ?? '')
                  : (achievement.badge_path_lock ?? '')
              "
              :alt="achievement.badge_id || 'Achievement badge'"
            />
          </a>
        </v-avatar>
      </template>
      <template #subtitle>
        <v-list-item-subtitle>
          {{ achievement.description?.toString() }}
        </v-list-item-subtitle>
        <v-chip
          v-if="isAchievementEarned(achievement) && smAndDown"
          label
          size="x-small"
          class="mt-1"
        >
          {{ getAchievementEarnedDate(achievement) }}
        </v-chip>
      </template>
      <template v-if="isAchievementEarned(achievement) && !smAndDown" #append>
        <v-chip label size="small">
          {{ getAchievementEarnedDate(achievement) }}
        </v-chip>
      </template>
    </v-list-item>
  </v-list>
</template>

<style scoped>
.locked {
  border-left: solid rgba(var(--v-theme-toplayer)) 4px;
}
.earned {
  border-left: solid rgba(var(--v-theme-primary)) 4px;
}
.earned-hardcore {
  border-left: solid rgba(var(--v-theme-romm-gold)) 4px;
}
.hidden {
  display: none;
}
</style>
