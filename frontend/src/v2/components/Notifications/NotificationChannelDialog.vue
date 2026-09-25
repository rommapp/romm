<script setup lang="ts">
// NotificationChannelDialog: adds a channel, or edits one, where a blank URL
// or secret keeps what the channel already has. Admins also get every Apprise
// service, each with the fields it takes.
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
  AppriseServiceSchema,
  NotificationChannelMinLevel,
  NotificationChannelSchema,
  NotificationChannelType,
  NotificationChannelUpdatePayload,
  NotificationTopic,
} from "@/__generated__";
import notificationChannelApi, {
  type NotificationChannelCreatePayload,
} from "@/services/api/notificationChannel";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import AppriseServiceFields from "@/v2/components/Notifications/AppriseServiceFields.vue";
import { useCan } from "@/v2/composables/useCan";
import { errorMessage } from "@/v2/utils/errorMessage";
import {
  type AppriseFieldValue,
  CHANNEL_ICONS,
  CHANNEL_LEVELS,
  CHANNEL_TOPICS,
  NOTIFICATION_CHANNEL_ADDRESS_MAX_LENGTH,
  NOTIFICATION_CHANNEL_NAME_MAX_LENGTH,
  NOTIFICATION_CHANNEL_SECRET_MAX_LENGTH,
  NOTIFICATION_CHANNEL_URL_MAX_LENGTH,
  appriseFieldsPayload,
  initialAppriseValues,
  missingAppriseLists,
} from "@/v2/utils/notificationChannels";
import { email as emailRule, notBlank } from "@/v2/utils/validation";

const props = defineProps<{ channel: NotificationChannelSchema | null }>();
const show = defineModel<boolean>({ required: true });
const emit = defineEmits<{
  saved: [channel: NotificationChannelSchema];
}>();

// The picker holds "webhook", "email", or an Apprise service as "apprise:<id>".
const APPRISE_PREFIX = "apprise:";

const { t } = useI18n();
const auth = storeAuth();
const heartbeat = storeHeartbeat();
const isAdmin = useCan("app.admin");

const formRef = ref<InstanceType<typeof RForm> | null>(null);
const kind = ref("webhook");
const name = ref("");
const url = ref("");
const secret = ref("");
const removeSecret = ref(false);
const address = ref("");
const minLevel = ref<NotificationChannelMinLevel>("info");
const topics = ref<NotificationTopic[]>([]);
const services = ref<AppriseServiceSchema[] | null>(null);
const loadingServices = ref(false);
const appriseValues = ref<Record<string, AppriseFieldValue>>({});
const missingLists = ref<string[]>([]);
const saving = ref(false);
const error = ref<string | null>(null);

const editing = computed(() => props.channel !== null);
const emailEnabled = computed(
  () => heartbeat.value.NOTIFICATIONS.EMAIL_ENABLED,
);
const keepsSecret = computed(() => !!props.channel?.has_secret);
const type = computed<NotificationChannelType>(() =>
  kind.value.startsWith(APPRISE_PREFIX)
    ? "apprise"
    : (kind.value as NotificationChannelType),
);
const service = computed(() => {
  if (type.value !== "apprise") return null;
  const id = kind.value.slice(APPRISE_PREFIX.length);
  return services.value?.find((s) => s.id === id) ?? null;
});

const typeItems = computed(() => [
  { title: t("notifications.channel-type-webhook"), value: "webhook" },
  {
    title: t("notifications.channel-type-email"),
    value: "email",
    disabled: !emailEnabled.value,
  },
  ...(services.value ?? []).map((s) => ({
    title: s.name,
    value: `${APPRISE_PREFIX}${s.id}`,
  })),
]);

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

const isHttpUrl = (value: string) => /^https?:\/\/\S+$/i.test(value.trim());
const nameRules = [notBlank()];
const urlRules = computed(() => [
  (value: string) =>
    (editing.value && !value.trim()) ||
    isHttpUrl(value) ||
    t("notifications.channel-url-invalid"),
]);
const addressRules = [notBlank(), emailRule];

async function loadServices() {
  if (!isAdmin.value || services.value || loadingServices.value) return;
  loadingServices.value = true;
  try {
    const { data } = await notificationChannelApi.getAppriseServices();
    services.value = data;
  } catch (err) {
    console.error("Could not load the Apprise services:", err);
    error.value = errorMessage(err, t("notifications.channel-services-failed"));
  } finally {
    loadingServices.value = false;
  }
}

// A service's fields start from its defaults, or from the channel being edited.
function resetAppriseValues() {
  appriseValues.value = service.value
    ? initialAppriseValues(service.value, props.channel?.fields ?? null)
    : {};
  missingLists.value = [];
}

watch(service, resetAppriseValues);

watch(show, (open) => {
  if (!open) return;
  const channel = props.channel;
  kind.value =
    channel?.type === "apprise"
      ? `${APPRISE_PREFIX}${channel.service}`
      : (channel?.type ?? "webhook");
  name.value = channel?.name ?? "";
  url.value = "";
  secret.value = "";
  removeSecret.value = false;
  address.value =
    channel?.type === "email" ? channel.target : (auth.user?.email ?? "");
  minLevel.value = channel?.min_level ?? "info";
  topics.value = channel?.topics ? [...channel.topics] : [];
  error.value = null;
  resetAppriseValues();
  formRef.value?.resetValidation();
  void loadServices();
});

function targetChanges(): NotificationChannelUpdatePayload {
  switch (type.value) {
    case "email":
      return { address: address.value.trim() };
    case "apprise":
      return service.value
        ? { fields: appriseFieldsPayload(service.value, appriseValues.value) }
        : {};
  }
  const changes: NotificationChannelUpdatePayload = {};
  if (url.value.trim()) changes.url = url.value.trim();
  if (removeSecret.value) changes.secret = "";
  else if (secret.value) changes.secret = secret.value;
  return changes;
}

function commonFields() {
  return {
    name: name.value.trim(),
    min_level: minLevel.value,
    topics: topics.value.length > 0 ? topics.value : null,
  };
}

function createPayload(): NotificationChannelCreatePayload {
  const fields = commonFields();
  if (type.value === "email") {
    return { type: "email", address: address.value.trim(), ...fields };
  }
  if (service.value) {
    return {
      type: "apprise",
      service: service.value.id,
      fields: appriseFieldsPayload(service.value, appriseValues.value),
      ...fields,
    };
  }
  return {
    type: "webhook",
    url: url.value.trim(),
    secret: secret.value || null,
    ...fields,
  };
}

async function request() {
  if (!props.channel) return notificationChannelApi.create(createPayload());
  return notificationChannelApi.update(props.channel.id, {
    ...commonFields(),
    ...targetChanges(),
  });
}

async function save() {
  const result = await formRef.value?.validate();
  missingLists.value = service.value
    ? missingAppriseLists(service.value, appriseValues.value)
    : [];
  if (!result?.valid || missingLists.value.length > 0) return;
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

        <div :class="{ 'r-v2-channel-dialog__pair': !editing }">
          <RSelect
            v-if="!editing"
            v-model="kind"
            :items="typeItems"
            :prepend-inner-icon="CHANNEL_ICONS[type]"
            :loading="loadingServices"
            :searchable="isAdmin"
            :search-placeholder="t('notifications.channel-search-services')"
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
        </div>

        <template v-if="type === 'webhook'">
          <RTextField
            v-model="url"
            :rules="urlRules"
            :maxlength="NOTIFICATION_CHANNEL_URL_MAX_LENGTH"
            :placeholder="
              editing ? channel?.target : 'https://example.com/hooks/romm'
            "
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
              {{ t("notifications.channel-secret") }}
            </template>
          </RTextField>
          <RCheckbox
            v-if="keepsSecret"
            v-model="removeSecret"
            :label="t('notifications.channel-secret-remove')"
          />
        </template>

        <template v-else-if="type === 'apprise'">
          <template v-if="service">
            <AppriseServiceFields
              v-model="appriseValues"
              :service="service"
              :editing="editing"
              :missing="missingLists"
            />
            <a
              v-if="service.setup_url"
              :href="service.setup_url"
              target="_blank"
              rel="noopener noreferrer"
              class="r-v2-channel-dialog__docs"
            >
              {{
                t("notifications.channel-setup-guide", {
                  service: service.name,
                })
              }}
              <RIcon icon="mdi-open-in-new" size="12" />
            </a>
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
            <RIcon :icon="CHANNEL_ICONS.email" size="14" />
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

.r-v2-channel-dialog__docs {
  display: inline-flex;
  align-items: center;
  align-self: flex-start;
  gap: 6px;
  margin-top: calc(-1 * var(--r-space-2));
  font-size: 12px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-brand-primary);
  text-decoration: none;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

.r-v2-channel-dialog__docs:hover {
  color: var(--r-color-fg);
  text-decoration: underline;
}
</style>
