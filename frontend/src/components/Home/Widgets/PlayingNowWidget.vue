<script setup lang="ts">
// PlayingNowWidget: one game someone is playing right now, linking to Active
// Sessions. WidgetBar drops it while nobody plays, so there is always a pick.
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import CachedPlatformIcon from "@/components/shared/CachedPlatformIcon.vue";
import GameCover from "@/components/shared/GameCover.vue";
import { useWebpSupport } from "@/composables/useWebpSupport";
import { RAvatar, RChip } from "@/lib";
import { ROUTES } from "@/plugins/router";
import storeActivity from "@/stores/activity";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { userAvatarUrl } from "@/utils/userAvatar";
import WidgetCard from "./WidgetCard.vue";
import { pickPlayingNow } from "./playingNow";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const { toWebp } = useWebpSupport();
const { activities } = storeToRefs(storeActivity());

const pick = computed(() => pickPlayingNow(activities.value));
const lead = computed(() => pick.value?.lead ?? null);

const coverSrc = computed(() =>
  lead.value?.rom_cover_path
    ? `${FRONTEND_RESOURCES_PATH}/${toWebp(lead.value.rom_cover_path)}`
    : null,
);

const avatarSrc = computed(() =>
  userAvatarUrl({
    userId: lead.value?.user_id,
    avatarPath: lead.value?.avatar_path,
    updatedAt: undefined,
  }),
);

const otherPlayers = computed(() => (pick.value?.playerCount ?? 1) - 1);
</script>

<template>
  <WidgetCard v-if="pick && lead" :title="t('home.widget-playing-now')">
    <template #action>
      <RChip
        class="r-widget-live__chip"
        size="x-small"
        variant="flat"
        color="danger"
        label
        prepend-icon="mdi-access-point"
      >
        {{ t("home.live-session-live") }}
      </RChip>
    </template>
    <router-link
      class="r-widget-live__body"
      :to="{ name: ROUTES.ACTIVITY }"
      :title="t('home.widget-playing-now-open')"
    >
      <GameCover
        :rom="null"
        :cover-src="coverSrc"
        :title="lead.rom_name"
        class="r-widget-live__cover"
        responsive
      />
      <div class="r-widget-live__info">
        <div class="r-widget-live__name">{{ lead.rom_name }}</div>
        <div class="r-widget-live__platform">
          <CachedPlatformIcon
            :slug="lead.platform_slug"
            :name="lead.platform_name"
            :size="14"
          />
          <span class="r-widget-live__ellipsis">{{ lead.platform_name }}</span>
        </div>
        <div class="r-widget-live__meta">
          <span class="r-widget-live__player">
            <RAvatar :image="avatarSrc" size="16" />
            <span class="r-widget-live__ellipsis">{{ lead.username }}</span>
            <span v-if="otherPlayers > 0">+{{ otherPlayers }}</span>
          </span>
          <span v-if="pick.otherGames > 0" class="r-widget-live__more">
            {{ t("home.widget-playing-now-more", { count: pick.otherGames }) }}
          </span>
        </div>
      </div>
    </router-link>
  </WidgetCard>
</template>

<style scoped>
.r-widget-live__chip {
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: var(--r-font-weight-bold);
}

.r-widget-live__chip :deep(.r-icon) {
  animation: r-widget-live-pulse 1.6s ease-in-out infinite;
}

@keyframes r-widget-live-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@media (prefers-reduced-motion: reduce) {
  .r-widget-live__chip :deep(.r-icon) {
    animation: none;
  }
}

.r-widget-live__body {
  display: flex;
  gap: 10px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: inherit;
  text-decoration: none;
  border-radius: var(--r-radius-sm);
}

/* Same sizing as the other widgets' covers: fixed height, natural width. */
.r-widget-live__body .r-widget-live__cover {
  height: 70px;
  width: auto;
  flex-shrink: 0;
  --r-cover-radius: var(--r-radius-sm);
}

.r-widget-live__info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.r-widget-live__name {
  font-size: 12.5px;
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.2;
  color: var(--r-color-fg);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

html:not([data-input="pad"]) .r-widget-live__body:hover .r-widget-live__name,
.r-widget-live__body:focus-visible .r-widget-live__name {
  color: var(--r-color-brand-primary);
}

.r-widget-live__platform,
.r-widget-live__player {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
}

.r-widget-live__platform {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-widget-live__ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.r-widget-live__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: auto;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}

.r-widget-live__more {
  flex-shrink: 0;
  color: var(--r-color-fg-faint);
}
</style>
