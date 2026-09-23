<script setup lang="ts">
// NotificationChannelsSection: the user's webhooks and email addresses, each
// forwarding the notifications its filters let through.
import {
  RAvatar,
  RBtn,
  REmptyState,
  RIcon,
  RSkeletonBlock,
  RSwitch,
  RTextField,
} from "@v2/lib";
import { onMounted, reactive, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { NotificationChannelSchema } from "@/__generated__";
import notificationChannelApi from "@/services/api/notificationChannel";
import { formatRelativeDate } from "@/utils";
import NotificationChannelDialog from "@/v2/components/Notifications/NotificationChannelDialog.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useGridNav } from "@/v2/composables/useGridNav";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { channelIcon } from "@/v2/utils/notificationChannels";

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();

const channels = ref<NotificationChannelSchema[]>([]);
const loaded = ref(false);
const dialogOpen = ref(false);
const editing = ref<NotificationChannelSchema | null>(null);
const busy = reactive(new Set<number>());
const codes = reactive<Record<number, string>>({});

const listRoot = ref<HTMLElement | null>(null);
useGridNav(listRoot, {
  rowSelector: ".r-v2-channel",
  getCells: (row) =>
    Array.from(
      row.querySelectorAll<HTMLElement>(
        "button:not([disabled]), input:not([disabled])",
      ),
    ),
});

function detailOf(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    .response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

async function load() {
  try {
    const { data } = await notificationChannelApi.getChannels();
    channels.value = data;
  } catch (error) {
    console.error("Could not load notification channels:", error);
    snackbar.error(t("notifications.channels-load-failed"));
  } finally {
    loaded.value = true;
  }
}

onMounted(load);

function replace(channel: NotificationChannelSchema) {
  channels.value = channels.value.map((c) =>
    c.id === channel.id ? channel : c,
  );
}

function openDialog(channel: NotificationChannelSchema | null) {
  editing.value = channel;
  dialogOpen.value = true;
}

function onSaved(channel: NotificationChannelSchema, created: boolean) {
  const before = channels.value.find((c) => c.id === channel.id);
  if (!created) {
    replace(channel);
  } else {
    channels.value = [...channels.value, channel];
  }
  // A code only goes out for an address that's new to the channel.
  if (!channel.confirmed && before?.target !== channel.target) {
    snackbar.info(
      t("notifications.channel-code-sent", { address: channel.target }),
      { icon: "mdi-email-fast-outline" },
    );
  } else {
    snackbar.success(t("notifications.channel-saved"));
  }
}

function filtersLabel(channel: NotificationChannelSchema): string {
  const level = t(
    `notifications.channel-level-${
      channel.min_level === "success" ? "info" : channel.min_level
    }`,
  );
  const topics = channel.topics
    ? channel.topics
        .map((topic) => t(`notifications.topic-${topic}`))
        .join(", ")
    : t("notifications.channel-topics-all");
  return `${level} · ${topics}`;
}

// Optimistic: the switch flips at once and flips back if the server refuses.
async function toggle(channel: NotificationChannelSchema, enabled: boolean) {
  replace({ ...channel, enabled });
  try {
    const { data } = await notificationChannelApi.update(channel.id, {
      enabled,
    });
    replace(data);
  } catch (error) {
    console.error("Could not update notification channel:", error);
    replace(channel);
    snackbar.error(t("notifications.channel-update-failed"));
  }
}

async function sendTest(channel: NotificationChannelSchema) {
  busy.add(channel.id);
  try {
    const { data } = await notificationChannelApi.test(channel.id);
    if (data.ok) {
      snackbar.success(t("notifications.channel-test-ok"));
    } else {
      snackbar.error(
        t("notifications.channel-test-failed", { error: data.error ?? "" }),
      );
    }
    await load();
  } catch (error) {
    console.error("Could not test notification channel:", error);
    snackbar.error(
      detailOf(error, t("notifications.channel-test-failed", { error: "" })),
    );
  } finally {
    busy.delete(channel.id);
  }
}

async function confirmCode(channel: NotificationChannelSchema) {
  const code = (codes[channel.id] ?? "").trim();
  if (!code) return;
  busy.add(channel.id);
  try {
    const { data } = await notificationChannelApi.confirm(channel.id, code);
    replace(data);
    delete codes[channel.id];
    snackbar.success(t("notifications.channel-confirmed"));
  } catch (error) {
    console.error("Could not confirm notification channel:", error);
    snackbar.error(detailOf(error, t("notifications.channel-confirm-failed")));
  } finally {
    busy.delete(channel.id);
  }
}

async function resendCode(channel: NotificationChannelSchema) {
  try {
    await notificationChannelApi.resendCode(channel.id);
    snackbar.info(
      t("notifications.channel-code-sent", { address: channel.target }),
      { icon: "mdi-email-fast-outline" },
    );
  } catch (error) {
    console.error("Could not resend the confirmation code:", error);
    snackbar.error(detailOf(error, t("notifications.channel-resend-failed")));
  }
}

async function remove(channel: NotificationChannelSchema) {
  const ok = await confirm({
    title: t("notifications.channel-delete-title", { name: channel.name }),
    body: t("notifications.channel-delete-body"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await notificationChannelApi.remove(channel.id);
    channels.value = channels.value.filter((c) => c.id !== channel.id);
  } catch (error) {
    console.error("Could not delete notification channel:", error);
    snackbar.error(t("notifications.channel-delete-failed"));
  }
}
</script>

<template>
  <div class="r-v2-channels">
    <div v-if="!loaded" class="r-v2-channels__list">
      <RSkeletonBlock
        v-for="n in 2"
        :key="`sk-${n}`"
        width="100%"
        height="72px"
        rounded="lg"
      />
    </div>

    <REmptyState
      v-else-if="channels.length === 0"
      icon="mdi-send-variant-outline"
      :title="t('notifications.channels-empty')"
      :hint="t('notifications.channels-empty-hint')"
    />

    <ul v-else ref="listRoot" class="r-v2-channels__list">
      <li
        v-for="channel in channels"
        :key="channel.id"
        class="r-v2-channel"
        :class="{ 'r-v2-channel--off': !channel.enabled }"
      >
        <div class="r-v2-channel__main">
          <RAvatar
            :icon="channelIcon(channel)"
            variant="translucent"
            size="36"
            class="r-v2-channel__icon"
          />
          <span class="r-v2-channel__text">
            <span class="r-v2-channel__name">{{ channel.name }}</span>
            <span class="r-v2-channel__target">{{ channel.target }}</span>
            <span class="r-v2-channel__meta">
              {{ filtersLabel(channel) }}
            </span>
            <span
              v-if="channel.last_error"
              class="r-v2-channel__meta r-v2-channel__meta--error"
            >
              <RIcon icon="mdi-alert-circle-outline" size="14" />
              {{
                t("notifications.channel-last-error", {
                  error: channel.last_error,
                })
              }}
            </span>
            <span
              v-else-if="channel.last_delivered_at"
              class="r-v2-channel__meta"
            >
              {{
                t("notifications.channel-last-sent", {
                  when: formatRelativeDate(channel.last_delivered_at),
                })
              }}
            </span>
          </span>
          <span class="r-v2-channel__actions">
            <RSwitch
              :model-value="channel.enabled"
              :disabled="!channel.confirmed"
              :aria-label="t('notifications.channel-enabled')"
              @update:model-value="toggle(channel, $event)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-send-check-outline"
              :loading="busy.has(channel.id)"
              :disabled="!channel.confirmed"
              :aria-label="t('notifications.channel-test')"
              @click="sendTest(channel)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-pencil-outline"
              :aria-label="t('notifications.channel-edit')"
              @click="openDialog(channel)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-delete-outline"
              color="danger"
              :aria-label="t('notifications.channel-delete')"
              @click="remove(channel)"
            />
          </span>
        </div>

        <div v-if="!channel.confirmed" class="r-v2-channel__confirm">
          <span class="r-v2-channel__meta">
            {{ t("notifications.channel-awaiting-code") }}
          </span>
          <div class="r-v2-channel__code">
            <RTextField
              v-model="codes[channel.id]"
              class="r-v2-channel__code-input"
              :placeholder="t('notifications.channel-code')"
              :aria-label="t('notifications.channel-code')"
              inputmode="numeric"
              autocomplete="one-time-code"
              :maxlength="16"
              density="compact"
              hide-details
              mono
              @keydown.enter="confirmCode(channel)"
            />
            <RBtn
              variant="flat"
              color="primary"
              size="small"
              :loading="busy.has(channel.id)"
              @click="confirmCode(channel)"
            >
              {{ t("common.confirm") }}
            </RBtn>
            <RBtn variant="text" size="small" @click="resendCode(channel)">
              {{ t("notifications.channel-resend") }}
            </RBtn>
          </div>
        </div>
      </li>
    </ul>

    <div class="r-v2-channels__footer">
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openDialog(null)"
      >
        {{ t("notifications.channel-add") }}
      </RBtn>
    </div>

    <NotificationChannelDialog
      v-model="dialogOpen"
      :channel="editing"
      @saved="onSaved"
    />
  </div>
</template>

<style scoped>
/* Bare Settings tab: the SettingsLayout content column owns the gutters. */
.r-v2-channels {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-channels__footer {
  display: flex;
  justify-content: flex-start;
}

.r-v2-channels__list {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.r-v2-channel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-3) var(--r-space-3) var(--r-space-3) var(--r-space-4);
  border-radius: var(--r-radius-card);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
}

.r-v2-channel--off .r-v2-channel__icon,
.r-v2-channel--off .r-v2-channel__text {
  opacity: 0.6;
}

.r-v2-channel__main {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
}

.r-v2-channel__icon {
  flex-shrink: 0;
}

.r-v2-channel__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-channel__name {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-channel__target {
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-secondary);
  overflow-wrap: anywhere;
}

.r-v2-channel__meta {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-v2-channel__meta--error {
  color: var(--r-color-danger);
  overflow-wrap: anywhere;
}

.r-v2-channel__actions {
  display: flex;
  align-items: center;
  gap: var(--r-space-1);
  flex-shrink: 0;
}

.r-v2-channel__confirm {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  padding-left: calc(36px + var(--r-space-3));
}

.r-v2-channel__code {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--r-space-2);
  max-width: 420px;
}

.r-v2-channel__code-input {
  flex: 1 1 140px;
  min-width: 0;
}

/* On a phone the actions drop under the text so the name keeps its width. */
html[data-bp~="xs"] .r-v2-channel__main {
  flex-wrap: wrap;
}
html[data-bp~="xs"] .r-v2-channel__actions {
  flex-basis: 100%;
  justify-content: flex-end;
}
html[data-bp~="xs"] .r-v2-channel__confirm {
  padding-left: 0;
}
</style>
