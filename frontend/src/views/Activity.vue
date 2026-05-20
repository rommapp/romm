<script setup lang="ts">
import { computed, onBeforeMount, onBeforeUnmount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import type { ActivityEntry } from "@/services/api/activity";
import storeActivity from "@/stores/activity";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

const { t } = useI18n();
const activityStore = storeActivity();
const now = ref(Date.now());
let tickTimer: ReturnType<typeof setInterval> | null = null;

onBeforeMount(async () => {
  activityStore.initSocket();
  await activityStore.fetchAll();
  // Update "elapsed time" labels every 30 seconds.
  tickTimer = setInterval(() => {
    now.value = Date.now();
  }, 30_000);
});

onBeforeUnmount(() => {
  if (tickTimer) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
});

const activities = computed(() =>
  [...activityStore.activities].sort(
    (a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  ),
);

function coverSrc(entry: ActivityEntry): string {
  if (!entry.rom_cover_path) return "";
  return `${FRONTEND_RESOURCES_PATH}/${entry.rom_cover_path}`;
}

function avatarSrc(entry: ActivityEntry): string {
  if (!entry.avatar_path) return "";
  return `/assets/${entry.avatar_path}`;
}

function elapsedLabel(startedAt: string): string {
  const started = new Date(startedAt).getTime();
  if (Number.isNaN(started)) return "";
  const diffMs = Math.max(0, now.value - started);
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return t("activity.just-now");
  if (minutes < 60) return t("activity.minutes-ago", { n: minutes });
  const hours = Math.floor(minutes / 60);
  const remMin = minutes % 60;
  if (hours < 24) {
    return remMin === 0
      ? t("activity.hours-ago", { n: hours })
      : t("activity.hours-minutes-ago", { h: hours, m: remMin });
  }
  const days = Math.floor(hours / 24);
  return t("activity.days-ago", { n: days });
}
</script>

<template>
  <v-container class="py-4">
    <div class="d-flex align-center mb-4">
      <v-icon class="mr-2" color="success">mdi-access-point</v-icon>
      <h2 class="text-h5 font-weight-medium">
        {{ t("activity.active-sessions") }}
      </h2>
      <v-chip
        v-if="activities.length > 0"
        class="ml-3"
        color="success"
        size="small"
        variant="tonal"
      >
        {{ activities.length }}
      </v-chip>
    </div>

    <v-alert
      v-if="activities.length === 0"
      type="info"
      variant="tonal"
      icon="mdi-information-outline"
    >
      {{ t("activity.no-activity") }}
    </v-alert>

    <v-row v-else>
      <v-col
        v-for="entry in activities"
        :key="`${entry.user_id}-${entry.device_id}`"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <router-link
          :to="{ name: ROUTES.ROM, params: { rom: entry.rom_id } }"
          class="activity-link"
        >
          <v-card variant="tonal" class="h-100">
            <div class="cover-wrapper">
              <v-img
                v-if="coverSrc(entry)"
                :src="coverSrc(entry)"
                :alt="entry.rom_name"
                aspect-ratio="2/3"
                cover
              />
              <div v-else class="cover-placeholder d-flex align-center justify-center">
                <v-icon size="48" color="grey-lighten-1">
                  mdi-nintendo-game-boy
                </v-icon>
              </div>
              <div class="cover-overlay">
                <v-chip
                  color="success"
                  variant="flat"
                  size="x-small"
                  class="live-chip"
                >
                  <v-icon start size="x-small">mdi-access-point</v-icon>
                  {{ t("activity.live") }}
                </v-chip>
              </div>
            </div>
            <v-card-text class="pa-3">
              <div class="text-body-2 font-weight-medium text-truncate">
                {{ entry.rom_name }}
              </div>
              <div class="text-caption text-medium-emphasis text-truncate">
                {{ entry.platform_name }}
              </div>
              <v-divider class="my-2" />
              <div class="d-flex align-center">
                <v-avatar size="24" class="mr-2">
                  <v-img
                    v-if="avatarSrc(entry)"
                    :src="avatarSrc(entry)"
                    :alt="entry.username"
                  />
                  <v-icon v-else size="small">mdi-account-circle</v-icon>
                </v-avatar>
                <div class="text-body-2 text-truncate">
                  {{ entry.username }}
                </div>
              </div>
              <div class="text-caption text-medium-emphasis mt-1">
                {{ elapsedLabel(entry.started_at) }}
                <span v-if="entry.device_type">
                  · {{ entry.device_type }}
                </span>
              </div>
            </v-card-text>
          </v-card>
        </router-link>
      </v-col>
    </v-row>
  </v-container>
</template>

<style scoped>
.activity-link {
  text-decoration: none;
  color: inherit;
  display: block;
  height: 100%;
}
.cover-wrapper {
  position: relative;
}
.cover-placeholder {
  aspect-ratio: 2 / 3;
  background-color: rgba(var(--v-theme-surface-variant, 0.08));
}
.cover-overlay {
  position: absolute;
  top: 8px;
  right: 8px;
}
.live-chip {
  box-shadow: 0 0 12px rgba(76, 175, 80, 0.6);
}
</style>
