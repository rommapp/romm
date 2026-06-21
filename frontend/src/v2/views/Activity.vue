<script setup lang="ts">
// Activity — live "who's playing what right now" board. Reads the
// activity store (hydrated once via REST, then kept current by the
// `activity:update` / `activity:clear` socket events the store binds in
// `initSocket`) and renders a responsive grid of ActivityCards.
//
// Elapsed-time labels are recomputed off a `now` ref that ticks every
// 30s, so "5m ago" advances without a full refetch. The grid is wired
// to `useWrapGridNav` so arrow keys / gamepad move across the cards.
import { RChip, RSkeletonBlock } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import type { ActivityEntry } from "@/services/api/activity";
import storeActivity from "@/stores/activity";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import ActivityCard from "@/v2/components/Activity/ActivityCard.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import PageHeader from "@/v2/components/shared/PageHeader.vue";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";
import { getMissingCoverImage } from "@/v2/utils/covers";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

const { t } = useI18n();
const activityStore = storeActivity();
const { toWebp } = useWebpSupport();
const { activities: rawActivities, initialized } = storeToRefs(activityStore);

const now = ref(Date.now());
let tickTimer: ReturnType<typeof setInterval> | null = null;

const gridRoot = ref<HTMLElement | null>(null);
useWrapGridNav(gridRoot, { cellSelector: ".activity-card" });

onMounted(async () => {
  activityStore.initSocket();
  await activityStore.fetchAll();
  // Refresh the elapsed-time labels every 30 seconds.
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

// Oldest session first so the longest-running players lead the board.
const activities = computed(() =>
  [...rawActivities.value].sort(
    (a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  ),
);

const loading = computed(() => !initialized.value);

function romRoute(entry: ActivityEntry) {
  return { name: ROUTES.ROM, params: { rom: entry.rom_id } };
}

function coverSrc(entry: ActivityEntry): string {
  if (!entry.rom_cover_path) return getMissingCoverImage(entry.rom_name);
  return `${FRONTEND_RESOURCES_PATH}/${toWebp(entry.rom_cover_path)}`;
}

function avatarSrc(entry: ActivityEntry): string {
  // ActivityEntry carries no `updated_at`; the avatar is stable for the
  // life of a session so cache-busting isn't needed here.
  return userAvatarUrl(entry.avatar_path, undefined);
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
  <div class="r-v2-activity">
    <PageHeader :title="t('activity.active-sessions')">
      <template #count>
        <RChip
          v-if="activities.length > 0"
          color="success"
          variant="translucent"
          size="small"
          prepend-icon="mdi-access-point"
        >
          {{ activities.length }}
        </RChip>
      </template>
    </PageHeader>

    <div v-if="loading" class="r-v2-activity__grid">
      <RSkeletonBlock
        v-for="n in 8"
        :key="`sk-${n}`"
        width="100%"
        height="260px"
        rounded="lg"
      />
    </div>

    <EmptyState
      v-else-if="activities.length === 0"
      variant="boxed"
      icon="mdi-access-point-off"
      :message="t('activity.no-activity')"
    />

    <div v-else ref="gridRoot" class="r-v2-activity__grid">
      <ActivityCard
        v-for="entry in activities"
        :key="`${entry.user_id}-${entry.device_id}`"
        :to="romRoute(entry)"
        :cover-src="coverSrc(entry)"
        :rom-name="entry.rom_name"
        :platform-name="entry.platform_name"
        :username="entry.username"
        :avatar-src="avatarSrc(entry)"
        :elapsed-label="elapsedLabel(entry.started_at)"
        :device-type="entry.device_type"
        :live-label="t('activity.live')"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-activity {
  padding: 32px var(--r-row-pad) 60px;
}

.r-v2-activity__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 20px 16px;
}

html[data-bp~="xs"] .r-v2-activity {
  padding: 16px var(--r-row-pad) 80px;
}
html[data-bp~="xs"] .r-v2-activity__grid {
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px 10px;
}
</style>
