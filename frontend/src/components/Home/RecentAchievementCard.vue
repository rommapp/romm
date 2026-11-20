<script setup lang="ts">
// RecentAchievementCard: one freshly unlocked RetroAchievements badge on Home.
// The art is the badge. The small mark is the game's ImageIcon, and it is
// the piece that morphs into the achievements page, same as a platform icon.
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { useBackgroundArt } from "@/composables/useBackgroundArt";
import { useViewTransition } from "@/composables/useViewTransition";
import { useWebpSupport } from "@/composables/useWebpSupport";
import { RImage, RSkeletonBlock } from "@/lib";
import { ROUTES } from "@/plugins/router";

export interface RecentAchievementItem {
  id: string;
  title: string | null;
  badgePath: string | null;
  badgeUrl: string | null;
  romId: number;
  romName: string;
  gameIconUrl: string | null;
  pathCoverLarge: string | null;
  pathCoverSmall: string | null;
  urlCover: string | null;
}

const props = defineProps<{ item: RecentAchievementItem }>();

const router = useRouter();
const setBgArt = useBackgroundArt();
const { morphTransition } = useViewTransition();
const { toWebp } = useWebpSupport();
const gameIconEl = ref<HTMLElement | null>(null);
const badgeBroken = ref(false);
const useRemoteBadge = ref(false);
const iconBroken = ref(false);

const badgeSrc = computed(() => {
  if (badgeBroken.value) return "";
  if (!useRemoteBadge.value && props.item.badgePath)
    return props.item.badgePath;
  return props.item.badgeUrl ?? "";
});

const showGameIcon = computed(
  () => Boolean(props.item.gameIconUrl) && !iconBroken.value,
);

function onBadgeError() {
  if (props.item.badgePath && props.item.badgeUrl && !useRemoteBadge.value) {
    useRemoteBadge.value = true;
    return;
  }
  badgeBroken.value = true;
}

function backdropUrl() {
  const local = props.item.pathCoverLarge || props.item.pathCoverSmall;
  if (local) return toWebp(local);
  return props.item.urlCover || props.item.gameIconUrl || null;
}

function onHighlight() {
  const url = backdropUrl();
  if (url) setBgArt(url);
}

function open() {
  const go = () =>
    router.push({
      name: ROUTES.ACHIEVEMENTS,
      query: { rom: String(props.item.romId) },
    });
  const icon = gameIconEl.value;
  if (icon) {
    morphTransition({ el: icon, name: `ach-icon-${props.item.romId}` }, go);
    return;
  }
  void go();
}
</script>

<template>
  <button
    type="button"
    class="r-ach-card"
    :data-focus-key="`ach-recent-${item.romId}-${item.id}`"
    :aria-label="item.title ? `${item.title}, ${item.romName}` : item.romName"
    @click="open"
    @mouseenter="onHighlight"
    @focus="onHighlight"
  >
    <span class="r-ach-card__art">
      <span v-if="badgeSrc" class="r-ach-card__badge">
        <RImage
          :src="badgeSrc"
          alt=""
          width="100%"
          height="100%"
          contain
          @error="onBadgeError"
        >
          <template #loading>
            <RSkeletonBlock width="100%" height="100%" rounded="lg" />
          </template>
        </RImage>
      </span>
      <span v-if="showGameIcon" ref="gameIconEl" class="r-ach-card__game-icon">
        <RImage
          :src="item.gameIconUrl ?? ''"
          alt=""
          width="100%"
          height="100%"
          cover
          @error="iconBroken = true"
        >
          <template #loading>
            <RSkeletonBlock width="100%" height="100%" rounded="none" />
          </template>
        </RImage>
      </span>
    </span>
    <span v-if="item.title" class="r-ach-card__title">{{ item.title }}</span>
    <span class="r-ach-card__game">{{ item.romName }}</span>
  </button>
</template>

<style scoped>
.r-ach-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  width: 150px;
  flex-shrink: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--r-color-fg);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.r-ach-card__art {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-lg);
  background: var(--r-color-surface);
  box-shadow: var(--r-elev-1);
  transition: transform var(--r-motion-fast);
}

.r-ach-card__badge {
  position: absolute;
  left: 11%;
  top: 11%;
  width: 78%;
  height: 78%;
}

.r-ach-card__badge :deep(.r-image) {
  display: block;
  width: 100%;
  height: 100%;
}

.r-ach-card__art :deep(.r-image__layer > .r-skeleton),
.r-ach-card__game-icon :deep(.r-image__layer > .r-skeleton) {
  position: absolute;
  inset: 0;
}

.r-ach-card__game-icon {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  overflow: hidden;
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg);
  box-shadow: 0 0 0 1px var(--r-color-border);
}

.r-ach-card__game-icon :deep(.r-image) {
  position: absolute;
  inset: 0;
}

html:not([data-input="pad"]) .r-ach-card:hover .r-ach-card__art,
.r-ach-card:focus-visible .r-ach-card__art {
  transform: scale(1.05);
}

.r-ach-card:focus-visible {
  outline: none;
}

.r-ach-card:focus-visible .r-ach-card__art {
  box-shadow:
    var(--r-elev-3),
    0 0 0 2px var(--r-color-brand-primary);
}

.r-ach-card__title {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.r-ach-card__game {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
</style>
