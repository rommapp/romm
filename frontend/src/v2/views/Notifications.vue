<script setup lang="ts">
// Notifications: the signed-in user's inbox. Whatever it shows is marked read,
// and a row that was unread keeps its accent until the user leaves.
import { RAvatar, RBtn, REmptyState, RSkeletonBlock } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, nextTick, reactive, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { RouterLink } from "vue-router";
import type { NotificationActorSchema } from "@/__generated__";
import AssetTimestamp from "@/v2/components/shared/AssetTimestamp.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useLoadingPhase } from "@/v2/composables/useLoadingPhase";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import storeNotificationInbox from "@/v2/stores/notificationInbox";
import { describeNotification } from "@/v2/utils/notifications";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

const { t } = useI18n();
const inbox = storeNotificationInbox();
const { notifications, loaded } = storeToRefs(inbox);
const snackbar = useSnackbar();
const confirm = useConfirm();

const listRoot = ref<HTMLElement | null>(null);
// A row without a link has the dismiss button as its only stop.
useGridNav(listRoot, {
  rowSelector: ".r-v2-notification",
  getCells: (row) =>
    Array.from(row.querySelectorAll<HTMLElement>("a, button:not([disabled])")),
});

const rows = computed(() =>
  notifications.value.map((notification) => ({
    notification,
    view: describeNotification(notification),
  })),
);

const phase = useLoadingPhase(
  () => !loaded.value,
  () => notifications.value.length === 0,
);

const unreadThisVisit = reactive(new Set<number>());

watch(
  () => notifications.value.filter((n) => !n.read_at).map((n) => n.id),
  (ids) => {
    if (ids.length === 0) return;
    ids.forEach((id) => unreadThisVisit.add(id));
    inbox.markRead(ids).catch((error) => {
      console.error("Could not mark notifications read:", error);
    });
  },
  { immediate: true },
);

function actorAvatar(actor: NotificationActorSchema): string {
  return userAvatarUrl({
    userId: actor.id,
    avatarPath: actor.avatar_path,
    updatedAt: actor.updated_at,
  });
}

// Keeps keyboard and gamepad focus in the list once its row is gone.
function focusDismissAt(index: number) {
  const buttons = listRoot.value?.querySelectorAll<HTMLElement>(
    ".r-v2-notification__dismiss",
  );
  if (!buttons?.length) return;
  buttons[Math.min(index, buttons.length - 1)].focus();
}

async function dismiss(id: number, index: number) {
  const pending = inbox.dismiss(id);
  void nextTick(() => focusDismissAt(index));
  try {
    await pending;
  } catch (error) {
    console.error("Could not dismiss notification:", error);
    snackbar.error(t("notifications.dismiss-failed"));
  }
}

const dismissingAll = ref(false);

async function dismissAll() {
  const ok = await confirm({
    title: t("notifications.dismiss-all-title"),
    body: t("notifications.dismiss-all-body"),
    confirmText: t("notifications.dismiss-all"),
    tone: "danger",
  });
  if (!ok) return;
  dismissingAll.value = true;
  try {
    await inbox.dismissAll();
  } catch (error) {
    console.error("Could not dismiss notifications:", error);
    snackbar.error(t("notifications.dismiss-failed"));
  } finally {
    dismissingAll.value = false;
  }
}
</script>

<template>
  <div class="r-v2-notifications">
    <div v-if="notifications.length > 0" class="r-v2-notifications__head">
      <RBtn
        variant="outlined"
        size="small"
        prepend-icon="mdi-notification-clear-all"
        :loading="dismissingAll"
        @click="dismissAll"
      >
        {{ t("notifications.dismiss-all") }}
      </RBtn>
    </div>

    <div v-if="phase === 'skeleton'" class="r-v2-notifications__list">
      <RSkeletonBlock
        v-for="n in 5"
        :key="`sk-${n}`"
        width="100%"
        height="68px"
        rounded="lg"
      />
    </div>

    <REmptyState
      v-else-if="phase === 'empty'"
      icon="mdi-bell-check-outline"
      :title="t('notifications.empty')"
      :hint="t('notifications.empty-hint')"
    />

    <ul
      v-else-if="phase === 'content'"
      ref="listRoot"
      class="r-v2-notifications__list"
    >
      <li
        v-for="({ notification, view }, i) in rows"
        :key="notification.id"
        class="r-v2-notification"
        :class="{
          'r-v2-notification--unread': unreadThisVisit.has(notification.id),
        }"
      >
        <component
          :is="view.to ? RouterLink : 'div'"
          :to="view.to ?? undefined"
          class="r-v2-notification__main"
        >
          <RAvatar
            :icon="view.icon"
            :color="notification.level"
            variant="translucent"
            size="36"
            class="r-v2-notification__icon"
          />
          <span class="r-v2-notification__text">
            <span class="r-v2-notification__title">{{ view.title }}</span>
            <span v-if="view.body" class="r-v2-notification__body">
              {{ view.body }}
            </span>
            <span v-if="notification.actor" class="r-v2-notification__actor">
              <RAvatar :image="actorAvatar(notification.actor)" size="16" />
              {{ notification.actor.username }}
            </span>
          </span>
          <AssetTimestamp
            :date="notification.created_at"
            align="end"
            class="r-v2-notification__time"
          />
        </component>
        <RBtn
          variant="text"
          size="small"
          icon="mdi-close"
          class="r-v2-notification__dismiss"
          :aria-label="t('common.dismiss')"
          @click="dismiss(notification.id, i)"
        />
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* Bare Settings route: the SettingsLayout content column owns the gutters. */
.r-v2-notifications {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}

.r-v2-notifications__head {
  display: flex;
  justify-content: flex-end;
}

.r-v2-notifications__list {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.r-v2-notification {
  position: relative;
  border-radius: var(--r-radius-card);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-notification--unread {
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 45%,
    transparent
  );
  background: color-mix(in srgb, var(--r-color-brand-primary) 8%, transparent);
}

.r-v2-notification--unread::before {
  content: "";
  position: absolute;
  top: 50%;
  left: 6px;
  width: 6px;
  height: 6px;
  border-radius: var(--r-radius-full);
  background: var(--r-color-brand-primary);
  transform: translateY(-50%);
}

.r-v2-notification__main {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  /* The right padding keeps the text clear of the dismiss button. */
  padding: var(--r-space-3) calc(var(--r-space-2) + 36px) var(--r-space-3)
    var(--r-space-4);
  border-radius: var(--r-radius-card);
  color: inherit;
  text-decoration: none;
}

a.r-v2-notification__main:hover {
  background: var(--r-color-surface-hover);
}

.r-v2-notification__icon {
  flex-shrink: 0;
}

.r-v2-notification__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-notification__title {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-notification__body {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  overflow-wrap: anywhere;
}

.r-v2-notification__actor {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
}

/* Centered by margins rather than a transform, which RBtn's press effect owns. */
.r-v2-notification .r-v2-notification__dismiss {
  position: absolute;
  top: 0;
  bottom: 0;
  right: var(--r-space-2);
  margin-block: auto;
  color: var(--r-color-fg-muted);
}

/* On a phone the time moves under the text so the title keeps the width. */
html[data-bp~="xs"] .r-v2-notification__main {
  flex-wrap: wrap;
  row-gap: var(--r-space-1);
}
html[data-bp~="xs"] .r-v2-notification__time {
  order: 3;
  flex-basis: 100%;
  padding-left: calc(36px + var(--r-space-3));
  align-items: flex-start;
}
</style>
