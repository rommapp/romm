<script setup lang="ts">
// ActivityCard: a single "now playing" entry in the Activity grid.
//
// Portrait cover (RImg) with a pulsing LIVE badge over the top-right,
// and a footer naming the game, its platform, and the player (avatar +
// username) with an elapsed-since label. The whole card is a RouterLink
// to the game detail view, so it participates in spatial / gamepad nav
// (useWrapGridNav discovers it via the `a[href]` it renders).
import { RAvatar, RChip, RIcon, RImg } from "@v2/lib";
import type { RouteLocationRaw } from "vue-router";

interface Props {
  to: RouteLocationRaw;
  coverSrc: string;
  romName: string;
  platformName: string;
  username: string;
  avatarSrc: string;
  elapsedLabel: string;
  deviceType: string;
  liveLabel: string;
}

defineProps<Props>();
</script>

<template>
  <router-link :to="to" class="activity-card">
    <div class="activity-card__cover">
      <RImg
        :src="coverSrc"
        :alt="romName"
        width="100%"
        aspect-ratio="2/3"
        cover
      />
      <RChip
        color="success"
        variant="flat"
        size="x-small"
        prepend-icon="mdi-access-point"
        class="activity-card__live"
      >
        {{ liveLabel }}
      </RChip>
    </div>

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
.activity-card {
  display: flex;
  flex-direction: column;
  text-decoration: none;
  color: inherit;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-card);
  overflow: hidden;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    transform var(--r-motion-fast) var(--r-motion-ease-out);
}

.activity-card:hover {
  background: var(--r-color-surface-hover);
  border-color: var(--r-color-border-strong);
  transform: translateY(-2px);
}

.activity-card__cover {
  position: relative;
}

.activity-card__live {
  position: absolute;
  top: 8px;
  right: 8px;
  /* Soft glow so the badge reads as "live" against any cover art. */
  box-shadow: 0 0 12px
    color-mix(in srgb, var(--r-color-success) 60%, transparent);
}

.activity-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px 12px;
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
