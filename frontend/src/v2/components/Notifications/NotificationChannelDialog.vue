<script setup lang="ts">
// NotificationChannelDialog: adds a channel, or edits one, where a blank URL
// or secret keeps what the channel already has.
import {
  RAlert,
  RBtn,
  RCheckbox,
  RDialog,
  RForm,
  RIcon,
  RSelect,
  RTextField,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  NotificationChannelMinLevel,
  NotificationChannelSchema,
  NotificationChannelType,
  NotificationChannelUpdatePayload,
  NotificationTopic,
  WebhookFormat,
} from "@/__generated__";
import notificationChannelApi from "@/services/api/notificationChannel";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import { errorMessage } from "@/v2/utils/errorMessage";
import {
  CHANNEL_LEVELS,
  CHANNEL_TOPICS,
  EMAIL_ICON,
  FORMAT_ICONS,
  NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH,
  NOTIFICATION_CHANNEL_NAME_MAX_LENGTH,
  NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH,
  NOTIFICATION_CHANNEL_URL_MAX_LENGTH,
} from "@/v2/utils/notificationChannels";
import { email as emailRule, notBlank } from "@/v2/utils/validation";

const props = defineProps<{ channel: NotificationChannelSchema | null }>();
const show = defineModel<boolean>({ required: true });
const emit = defineEmits<{
  saved: [channel: NotificationChannelSchema];
}>();

const { t } = useI18n();
const auth = storeAuth();
const heartbeat = storeHeartbeat();

const formRef = ref<InstanceType<typeof RForm> | null>(null);
const type = ref<NotificationChannelType>("webhook");
const format = ref<WebhookFormat>("json");
const name = ref("");
const url = ref("");
const secret = ref("");
const removeSecret = ref(false);
const address = ref("");
const minLevel = ref<NotificationChannelMinLevel>("info");
const topics = ref<NotificationTopic[]>([]);
const saving = ref(false);
const error = ref<string | null>(null);

const editing = computed(() => props.channel !== null);
const emailEnabled = computed(
  () => heartbeat.value.NOTIFICATIONS.EMAIL_ENABLED,
);
const keepsSecret = computed(() => !!props.channel?.has_secret);

const typeItems = computed(() => [
  { title: t("notifications.channel-type-webhook"), value: "webhook" },
  {
    title: t("notifications.channel-type-email"),
    value: "email",
    disabled: !emailEnabled.value,
  },
]);

const formatItems = computed(() =>
  (Object.keys(FORMAT_ICONS) as WebhookFormat[]).map((value) => ({
    title: t(`notifications.channel-format-${value}`),
    value,
  })),
);

const levelItems = computed(() =>
  CHANNEL_LEVELS.map((value) => ({
    title: t(`notifications.channel-level-${value}`),
    value,
  })),
);

const topicItems = computed(() =>
  CHANNEL_TOPICS.map((value) => ({
    title: t(`notifications.topic-${value}`),
    value,
  })),
);

const URL_PLACEHOLDERS: Record<WebhookFormat, string> = {
  json: "https://example.com/hooks/romm",
  discord: "https://discord.com/api/webhooks/…",
  ntfy: "https://ntfy.sh/your-topic",
};

const isHttpUrl = (value: string) => /^https?:\/\/\S+$/i.test(value.trim());
const nameRules = [notBlank()];
const urlRules = computed(() => [
  (value: string) =>
    (editing.value && !value.trim()) ||
    isHttpUrl(value) ||
    t("notifications.channel-url-invalid"),
]);
const addressRules = [notBlank(), emailRule];

watch(show, (open) => {
  if (!open) return;
  const channel = props.channel;
  type.value = channel?.type ?? "webhook";
  format.value = channel?.format ?? "json";
  name.value = channel?.name ?? "";
  url.value = "";
  secret.value = "";
  removeSecret.value = false;
  address.value =
    channel?.type === "email" ? channel.target : (auth.user?.email ?? "");
  minLevel.value = channel?.min_level ?? "info";
  topics.value = channel?.topics ? [...channel.topics] : [];
  error.value = null;
  formRef.value?.resetValidation();
});

function webhookChanges(): NotificationChannelUpdatePayload {
  const changes: NotificationChannelUpdatePayload = { format: format.value };
  if (url.value.trim()) changes.url = url.value.trim();
  if (removeSecret.value) changes.secret = "";
  else if (secret.value) changes.secret = secret.value;
  return changes;
}

async function request() {
  const filters = {
    min_level: minLevel.value,
    topics: topics.value.length > 0 ? topics.value : null,
  };
  if (props.channel) {
    return notificationChannelApi.update(props.channel.id, {
      name: name.value.trim(),
      ...filters,
      ...(props.channel.type === "webhook"
        ? webhookChanges()
        : { address: address.value.trim() }),
    });
  }
  return notificationChannelApi.create(
    type.value === "email"
      ? {
          type: "email",
          name: name.value.trim(),
          address: address.value.trim(),
          ...filters,
        }
      : {
          type: "webhook",
          name: name.value.trim(),
          url: url.value.trim(),
          format: format.value,
          secret: format.value === "discord" ? null : secret.value || null,
          ...filters,
        },
  );
}

async function save() {
  const result = await formRef.value?.validate();
  if (!result?.valid) return;
  saving.value = true;
  error.value = null;
  try {
    const { data } = await request();
    emit("saved", data);
    show.value = false;
  } catch (err) {
    console.error("Could not save the notification channel:", err);
    error.value = errorMessage(err, t("notifications.channel-save-failed"));
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-send-variant-outline"
    :width="560"
    scroll-content
    cancelable
    :cancel-disabled="saving"
  >
    <template #header>
      <span>
        {{
          editing
            ? t("notifications.channel-edit")
            : t("notifications.channel-new")
        }}
      </span>
    </template>

    <template #content>
      <RForm ref="formRef" class="r-v2-channel-dialog" @submit="save">
        <RAlert v-if="error" type="error" density="compact" :text="error" />

        <div class="r-v2-channel-dialog__pair">
          <RSelect
            v-if="!editing"
            v-model="type"
            :items="typeItems"
            :prepend-inner-icon="
              type === 'email' ? EMAIL_ICON : FORMAT_ICONS.json
            "
            :hint="
              emailEnabled
                ? undefined
                : t('notifications.channel-email-unavailable')
            "
            prefix-label="stacked"
          >
            <template #prefix-label>
              <RIcon icon="mdi-shape-outline" size="14" />
              {{ t("notifications.channel-type") }}
            </template>
          </RSelect>
          <RSelect
            v-if="type === 'webhook'"
            v-model="format"
            :items="formatItems"
            :prepend-inner-icon="FORMAT_ICONS[format]"
            prefix-label="stacked"
            hide-details
          >
            <template #prefix-label>
              <RIcon icon="mdi-code-json" size="14" />
              {{ t("notifications.channel-format") }}
            </template>
          </RSelect>
        </div>

        <RTextField
          v-model="name"
          :rules="nameRules"
          :maxlength="NOTIFICATION_CHANNEL_NAME_MAX_LENGTH"
          prefix-label="stacked"
          required
        >
          <template #prefix-label>
            <RIcon icon="mdi-tag-outline" size="14" />
            {{ t("notifications.channel-name") }}
          </template>
        </RTextField>

        <template v-if="type === 'webhook'">
          <RTextField
            v-model="url"
            :rules="urlRules"
            :maxlength="NOTIFICATION_CHANNEL_URL_MAX_LENGTH"
            :placeholder="editing ? channel?.target : URL_PLACEHOLDERS[format]"
            :hint="editing ? t('notifications.channel-url-keep') : undefined"
            autocomplete="off"
            prefix-label="stacked"
            mono
            :required="!editing"
          >
            <template #prefix-label>
              <RIcon icon="mdi-link-variant" size="14" />
              {{ t("notifications.channel-url") }}
            </template>
          </RTextField>

          <template v-if="format !== 'discord'">
            <RTextField
              v-model="secret"
              type="password"
              :maxlength="NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH"
              :disabled="removeSecret"
              :hint="
                keepsSecret ? t('notifications.channel-secret-keep') : undefined
              "
              autocomplete="new-password"
              prefix-label="stacked"
            >
              <template #prefix-label>
                <RIcon icon="mdi-key-outline" size="14" />
                {{ t(`notifications.channel-secret-${format}`) }}
              </template>
            </RTextField>
            <RCheckbox
              v-if="keepsSecret"
              v-model="removeSecret"
              :label="t('notifications.channel-secret-remove')"
            />
          </template>
        </template>

        <RTextField
          v-else
          v-model="address"
          type="email"
          :rules="addressRules"
          :maxlength="NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH"
          :hint="t('notifications.channel-address-hint')"
          autocomplete="email"
          prefix-label="stacked"
          required
        >
          <template #prefix-label>
            <RIcon :icon="EMAIL_ICON" size="14" />
            {{ t("notifications.channel-address") }}
          </template>
        </RTextField>

        <div class="r-v2-channel-dialog__pair">
          <RSelect
            v-model="minLevel"
            :items="levelItems"
            prefix-label="stacked"
            hide-details
          >
            <template #prefix-label>
              <RIcon icon="mdi-filter-outline" size="14" />
              {{ t("notifications.channel-min-level") }}
            </template>
          </RSelect>
          <RSelect
            v-model="topics"
            :items="topicItems"
            :placeholder="t('notifications.channel-topics-all')"
            multiple
            chips
            closable-chips
            prefix-label="stacked"
            hide-details
          >
            <template #prefix-label>
              <RIcon icon="mdi-format-list-checks" size="14" />
              {{ t("notifications.channel-topics") }}
            </template>
          </RSelect>
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-content-save-outline"
        :loading="saving"
        @click="save"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-channel-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-v2-channel-dialog__pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-channel-dialog__pair {
  grid-template-columns: minmax(0, 1fr);
}
</style>
