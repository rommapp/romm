<script setup lang="ts">
// Activity — live "who's playing what right now" board. Reads the
// activity store (hydrated once via REST, then kept current by the
// `activity:update` / `activity:clear` socket events the store binds in
// `initSocket`) and renders a responsive grid of ActivityCards.
//
// Elapsed-time labels are recomputed off a `now` ref that ticks every
// 30s, so "5m ago" advances without a full refetch. The grid is wired
// to `useWrapGridNav` so arrow keys / gamepad move across the cards.
import { RIcon, RSkeletonBlock, RTooltip } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import type { ActivityEntry } from "@/services/api/activity";
import storeActivity from "@/stores/activity";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import ActivityCard from "@/v2/components/Activity/ActivityCard.vue";
import EmptyState from "@/v2/components/shared/EmptyState.vue";
import { useWebpSupport } from "@/v2/composables/useWebpSupport";
import { useWrapGridNav } from "@/v2/composables/useWrapGridNav";
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

// Cover art URL, or null when the rom has no cover — GameCover then paints
// its own canonical placeholder (title initial).
function coverArtSrc(entry: ActivityEntry): string | null {
  if (!entry.rom_cover_path) return null;
  return `${FRONTEND_RESOURCES_PATH}/${toWebp(entry.rom_cover_path)}`;
}

// Main image: the "where they are" screenshot (already a full URL) if the
// session has one, else the cover art.
function coverSrc(entry: ActivityEntry): string | null {
  return entry.screenshot_path || coverArtSrc(entry);
}

// PIP cover-art thumbnail — only when a screenshot is the main image, so the
// game stays identifiable.
function pipCoverSrc(entry: ActivityEntry): string | null {
  return entry.screenshot_path ? coverArtSrc(entry) : null;
}

function avatarSrc(entry: ActivityEntry): string {
  // ActivityEntry carries no `updated_at`; the avatar is stable for the
  // life of a session so cache-busting isn't needed here.
  return userAvatarUrl(entry.user_id, entry.avatar_path, undefined);
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
    <!-- Counter top-left — keeps the live session total visible without the
         page-level header the other Settings sections don't carry. The label
         lives in a tooltip so the chip itself stays a compact icon + count;
         the dot pulses while at least one session is live. -->
    <div class="r-v2-activity__head">
      <div
        class="r-v2-activity__total"
        :class="{ 'r-v2-activity__total--live': activities.length > 0 }"
      >
        <RIcon
          icon="mdi-access-point"
          size="16"
          class="r-v2-activity__total-icon"
        />
        <span class="r-v2-activity__total-count">{{ activities.length }}</span>
        <RTooltip activator="parent" :text="t('activity.total-sessions')" />
      </div>
    </div>

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
        v-for="(entry, i) in activities"
        :key="`${entry.user_id}-${entry.device_id}`"
        class="r-v2-card-fade"
        :style="{ '--card-fade-i': i }"
        :to="romRoute(entry)"
        :cover-src="coverSrc(entry)"
        :pip-cover-src="pipCoverSrc(entry)"
        :rom-name="entry.rom_name"
        :platform-name="entry.platform_name"
        :username="entry.username"
        :avatar-src="avatarSrc(entry)"
        :elapsed-label="elapsedLabel(entry.started_at)"
        :device-type="entry.device_type"
      />
    </div>
  </div>
</template>

<style scoped>
/* Bare Settings route (no outer glass panel) — the SettingsLayout content
   column already owns the page gutters, so the view itself adds none. */
.r-v2-activity {
  display: flex;
  flex-direction: column;
}

/* Counter row — left-aligned stat replacing the page header. */
.r-v2-activity__head {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 20px;
}

.r-v2-activity__total {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  border-radius: var(--r-radius-pill);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  color: var(--r-color-fg-muted);
  cursor: default;
}

.r-v2-activity__total-icon {
  color: var(--r-color-fg-faint);
}
.r-v2-activity__total--live .r-v2-activity__total-icon {
  color: var(--r-color-success);
  /* Soft pulse while sessions are live — echoes the cards' LIVE chip. */
  animation: r-v2-activity-pulse 2s ease-in-out infinite;
}

.r-v2-activity__total-count {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-bold);
  font-variant-numeric: tabular-nums;
  color: var(--r-color-fg);
}
.r-v2-activity__total--live .r-v2-activity__total-count {
  color: var(--r-color-success);
}

@keyframes r-v2-activity-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}
@media (prefers-reduced-motion: reduce) {
  .r-v2-activity__total--live .r-v2-activity__total-icon {
    animation: none;
  }
}

/* Gallery-card flow: every card is the SAME height, its width set by the
   image's natural ratio (landscape screenshots wide, portrait covers narrow).
   A wrapping flex row gives that without a fixed-column grid (which would pin
   the width and leave ragged vertical gaps). */
.r-v2-activity__grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px 16px;
  align-items: flex-start;
}

html[data-bp~="xs"] .r-v2-activity__grid {
  gap: 16px 10px;
}
</style>
