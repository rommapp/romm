<script setup lang="ts">
// EventLogRow: one event on the event log's timeline, a fixed height so the
// list can window it.
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
  >
    <time
      class="r-v2-audit-event__time"
      :datetime="event.occurred_at"
      :title="formatTimestamp(event.occurred_at, locale)"
    >
      {{ time }}
    </time>
    <span class="r-v2-audit-event__rail">
      <RAvatar
        :icon="view.icon"
        :color="view.tone"
        variant="translucent"
        size="28"
        class="r-v2-audit-event__dot"
      />
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
        <span class="r-v2-audit-event__meta-item">
          <RAvatar
            :image="actorAvatar"
            :icon="actorIcon"
            variant="translucent"
            size="16"
          />
          {{ actorName }}
        </span>
        <span v-if="view.detail" class="r-v2-audit-event__meta-item">
          {{ view.detail }}
        </span>
        <span v-if="event.device_name" class="r-v2-audit-event__meta-item">
          <RIcon icon="mdi-devices" size="14" />
          {{ event.device_name }}
        </span>
        <span
          v-if="event.ip_address"
          class="r-v2-audit-event__meta-item r-v2-audit-event__ip"
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
  height: 62px;
  padding: var(--r-space-2) var(--r-space-4);
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
  top: calc(-1 * var(--r-space-2));
  bottom: calc(-1 * var(--r-space-2));
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

/* An opaque disc under the translucent icon keeps the rail from showing through. */
.r-v2-audit-event__dot {
  position: relative;
  box-shadow: 0 0 0 3px var(--r-color-surface);
  background-color: var(--r-color-surface);
}

.r-v2-audit-event__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
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

/* One line, so every row keeps the height the windowing counts on. */
.r-v2-audit-event__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

.r-v2-audit-event__meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  vertical-align: middle;
}
.r-v2-audit-event__meta-item + .r-v2-audit-event__meta-item {
  margin-inline-start: var(--r-space-3);
}

.r-v2-audit-event__ip {
  font-family: var(--r-font-family-mono);
}

html[data-bp~="xs"] .r-v2-audit-event {
  grid-template-columns: 2.75rem var(--r-audit-dot) minmax(0, 1fr);
  column-gap: var(--r-space-2);
  padding-inline: var(--r-space-3);
}
</style>
