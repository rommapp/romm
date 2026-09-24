<script setup lang="ts">
// EventLogRow: one event on the event log's timeline, at the height the list
// windows it at and in the geometry the list sets (EVENT_ROW_VARS).
import { RAvatar, RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink } from "vue-router";
import type { AuditEventSchema } from "@/__generated__";
import { formatTimestamp } from "@/utils";
import type { AuditEventView } from "@/v2/utils/auditEvents";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

const props = defineProps<{
  event: AuditEventSchema;
  view: AuditEventView;
  /** The day's first and last events close its panel and its rail. */
  first: boolean;
  last: boolean;
  /** The time of day it happened, formatted by the list for all its rows. */
  time: string;
  height: number;
}>();

const { t, locale } = useI18n();

const actorName = computed(() => {
  const { actor_kind, actor, actor_name } = props.event;
  if (actor_kind === "system") return t("audit.system");
  if (actor_kind === "anonymous") return t("audit.anonymous");
  return actor?.username ?? actor_name ?? t("audit.deleted-user");
});

const actorIcon = computed(() => {
  const { actor_kind, actor } = props.event;
  if (actor_kind === "system") return "mdi-robot-outline";
  if (actor_kind === "anonymous") return "mdi-incognito";
  return actor ? undefined : "mdi-account-off-outline";
});

const actorAvatar = computed(() => {
  const { actor } = props.event;
  if (!actor) return undefined;
  return userAvatarUrl({
    userId: actor.id,
    avatarPath: actor.avatar_path,
    updatedAt: actor.updated_at,
  });
});
</script>

<template>
  <div
    class="r-v2-audit-event"
    :class="{
      'r-v2-audit-event--first': first,
      'r-v2-audit-event--last': last,
    }"
    :style="{ height: `${height}px` }"
  >
    <time
      class="r-v2-audit-event__time"
      :datetime="event.occurred_at"
      :title="formatTimestamp(event.occurred_at, locale)"
    >
      {{ time }}
    </time>
    <span class="r-v2-audit-event__rail">
      <span
        class="r-v2-audit-event__dot"
        :style="{ '--r-audit-tone': view.tone }"
      >
        <RIcon :icon="view.icon" size="16" />
      </span>
    </span>
    <span class="r-v2-audit-event__body">
      <component
        :is="view.to ? RouterLink : 'span'"
        :to="view.to ?? undefined"
        class="r-v2-audit-event__title"
      >
        {{ view.title }}
      </component>
      <span class="r-v2-audit-event__meta">
        <span class="r-v2-audit-event__item r-v2-audit-event__actor">
          <RAvatar
            :image="actorAvatar"
            :icon="actorIcon"
            variant="translucent"
            size="16"
          />
          <span class="r-v2-audit-event__text">{{ actorName }}</span>
        </span>
        <span
          v-if="view.detail"
          class="r-v2-audit-event__item r-v2-audit-event__detail"
        >
          <span class="r-v2-audit-event__text">{{ view.detail }}</span>
        </span>
        <span
          v-if="event.device_name"
          class="r-v2-audit-event__item r-v2-audit-event__device"
        >
          <RIcon icon="mdi-devices" size="14" />
          <span class="r-v2-audit-event__text">{{ event.device_name }}</span>
        </span>
        <span
          v-if="event.ip_address"
          class="r-v2-audit-event__item r-v2-audit-event__ip"
        >
          <RIcon icon="mdi-ip-network-outline" size="14" />
          {{ event.ip_address }}
        </span>
      </span>
    </span>
  </div>
</template>

<style scoped>
/* Each day reads as one panel: its first and last rows round the corners. */
.r-v2-audit-event {
  --r-audit-dot: 28px;
  display: grid;
  grid-template-columns: 3.25rem var(--r-audit-dot) minmax(0, 1fr);
  column-gap: var(--r-space-3);
  box-sizing: border-box;
  padding: var(--r-audit-pad-block) var(--r-space-4);
  background: var(--r-color-surface);
  border-inline: 1px solid var(--r-color-border);
}
.r-v2-audit-event--first {
  border-top: 1px solid var(--r-color-border);
  border-start-start-radius: var(--r-radius-card);
  border-start-end-radius: var(--r-radius-card);
}
.r-v2-audit-event--last {
  border-bottom: 1px solid var(--r-color-border);
  border-end-start-radius: var(--r-radius-card);
  border-end-end-radius: var(--r-radius-card);
}

.r-v2-audit-event__time {
  padding-top: 5px;
  font-size: var(--r-font-size-sm);
  font-variant-numeric: tabular-nums;
  text-align: end;
  color: var(--r-color-fg-muted);
}

/* One rail joins the day's events through the middle of their icons. */
.r-v2-audit-event__rail {
  position: relative;
  display: flex;
  justify-content: center;
}
.r-v2-audit-event__rail::before {
  content: "";
  position: absolute;
  top: calc(-1 * var(--r-audit-pad-block));
  bottom: calc(-1 * var(--r-audit-pad-block));
  left: 50%;
  width: 2px;
  transform: translateX(-50%);
  background: var(--r-color-border);
}
.r-v2-audit-event--first .r-v2-audit-event__rail::before {
  top: calc(var(--r-audit-dot) / 2);
}
.r-v2-audit-event--last .r-v2-audit-event__rail::before {
  bottom: calc(100% - var(--r-audit-dot) / 2);
}

/* The page's own background is the one color that reads on every tone. */
.r-v2-audit-event__dot {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--r-audit-dot);
  height: var(--r-audit-dot);
  border-radius: 50%;
  background: var(--r-audit-tone);
  color: var(--r-color-bg);
}

.r-v2-audit-event__body {
  display: flex;
  flex-direction: column;
  gap: var(--r-audit-gap);
  min-width: 0;
  padding-top: 3px;
}

.r-v2-audit-event__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  text-decoration: none;
}

a.r-v2-audit-event__title:hover {
  text-decoration: underline;
}

/* Who, what, and where from, on one line; long names shorten rather than
   push what follows off the end. */
.r-v2-audit-event__meta {
  display: flex;
  gap: var(--r-space-3);
  overflow: hidden;
  white-space: nowrap;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

.r-v2-audit-event__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.r-v2-audit-event__actor,
.r-v2-audit-event__ip {
  flex-shrink: 0;
}

.r-v2-audit-event__text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-audit-event__ip {
  font-family: var(--r-font-family-mono);
}

html[data-bp~="xs"] .r-v2-audit-event {
  grid-template-columns: 2.75rem var(--r-audit-dot) minmax(0, 1fr);
  column-gap: var(--r-space-2);
  padding-inline: var(--r-space-3);
}
/* A phone stacks the title, the detail, who, and where from, in that order
   on every row; the list sizes each row for how its title and detail wrap. */
html[data-bp~="xs"] .r-v2-audit-event__body {
  padding-top: var(--r-audit-title-offset);
}
html[data-bp~="xs"] .r-v2-audit-event__title,
html[data-bp~="xs"] .r-v2-audit-event__detail .r-v2-audit-event__text {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: var(--r-audit-max-lines);
  line-clamp: var(--r-audit-max-lines);
  white-space: normal;
  overflow-wrap: anywhere;
}
html[data-bp~="xs"] .r-v2-audit-event__title {
  line-height: var(--r-audit-title-line);
}
html[data-bp~="xs"] .r-v2-audit-event__meta {
  flex-wrap: wrap;
  gap: var(--r-audit-gap) var(--r-space-3);
  line-height: var(--r-audit-meta-line);
}
html[data-bp~="xs"] .r-v2-audit-event__actor,
html[data-bp~="xs"] .r-v2-audit-event__detail {
  flex: 0 0 100%;
}
html[data-bp~="xs"] .r-v2-audit-event__detail {
  order: -1;
}
/* No basis, so a long device name shortens beside the address instead of
   wrapping it onto a line of its own. */
html[data-bp~="xs"] .r-v2-audit-event__device {
  flex: 1 1 0;
  max-width: max-content;
}
</style>
