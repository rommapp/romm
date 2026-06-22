<script setup lang="ts">
// ActivityCard: a single "now playing" entry in the Activity grid.
//
// Natural-aspect cover (GameCover) above a footer naming the game, its
// platform, and the player (avatar + username) with an elapsed-since label.
// The whole card is a RouterLink to the game detail view, so it participates
// in spatial / gamepad nav (useWrapGridNav discovers it via the `a[href]` it
// renders). No "live" badge: every card in this view is an active session by
// definition, so the badge carried no per-card information — the page's
// session counter is the single live indicator.
import { RAvatar, RIcon } from "@v2/lib";
import type { RouteLocationRaw } from "vue-router";
import GameCover from "@/v2/components/shared/GameCover.vue";

interface Props {
  to: RouteLocationRaw;
  coverSrc: string | null;
  romName: string;
  platformName: string;
  username: string;
  avatarSrc: string;
  elapsedLabel: string;
  deviceType: string;
}

defineProps<Props>();
</script>

<template>
  <router-link :to="to" class="activity-card">
    <!-- GameCover is the canonical cover-art box (shared with the gallery
         cards, detail hero, players): it measures the image's natural ratio on
         load and sizes the box to it, so the card adopts the cover's true shape
         with no background showing. A 2:3 box is reserved while loading to
         avoid a reflow. -->
    <GameCover
      :rom="null"
      :cover-src="coverSrc"
      :title="romName"
      class="activity-card__art"
    />

    <div class="activity-card__body">
      <div class="activity-card__rom" :title="romName">
        {{ romName }}
      </div>
      <div class="activity-card__platform" :title="platformName">
        {{ platformName }}
      </div>

      <div class="activity-card__player">
        <RAvatar :image="avatarSrc" size="x-small" />
        <span class="activity-card__username" :title="username">
          {{ username }}
        </span>
      </div>

      <div class="activity-card__meta">
        {{ elapsedLabel }}
        <template v-if="deviceType">
          <RIcon icon="mdi-circle-small" size="14" />
          <span class="activity-card__device">{{ deviceType }}</span>
        </template>
      </div>
    </div>
  </router-link>
</template>

<style scoped>
/* No card surface — the cover is the card (gallery-card vocabulary): a
   rounded art box that lifts on hover, with the title/meta stacked below on
   the bare page. */
.activity-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-decoration: none;
  color: inherit;
}

/* GameCover owns the radius / overflow / placeholder background; the card
   adds the hover lift (rise + shadow) on top. */
.activity-card__art {
  transition:
    transform var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.activity-card:hover .activity-card__art {
  transform: translateY(-4px);
  box-shadow: 0 12px 28px color-mix(in srgb, black 45%, transparent);
}

.activity-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.activity-card__rom {
  font-size: var(--r-font-size-sm);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-card__platform {
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-card__player {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  min-width: 0;
}

.activity-card__username {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.activity-card__meta {
  display: flex;
  align-items: center;
  margin-top: 4px;
  font-size: var(--r-font-size-xs);
  color: var(--r-color-fg-faint);
}

.activity-card__device {
  text-transform: capitalize;
}
</style>
