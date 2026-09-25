<script setup lang="ts">
// NotificationChannelDialog: adds or edits a channel, where a blank URL or secret
// keeps the current one. Admins also get every Apprise service and its fields.
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
import { watchDebounced } from "@vueuse/core";
import { computed, nextTick, ref, watch } from "vue";
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
  appriseFieldLabel,
  appriseFieldsPayload,
  initialAppriseValues,
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
const removedSecrets = ref<string[]>([]);
const pastedUrl = ref("");
const pasteError = ref<string | null>(null);
const filling = ref(false);
// The fields the last pasted URL filled in, so the form can show it did.
const filledFields = ref<string[]>([]);
const saving = ref(false);
const error = ref<string | null>(null);

const editing = computed(() => props.channel !== null);
const emailEnabled = computed(
  () => heartbeat.value.NOTIFICATIONS.EMAIL_ENABLED,
);
const keepsSecret = computed(() => !!props.channel?.has_secret);
const storedSecrets = computed(() => props.channel?.stored_secrets ?? []);
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
  if (props.channel && props.channel.type !== "apprise") return;
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
  removedSecrets.value = [];
  filledFields.value = [];
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
  clearPaste();
  formRef.value?.resetValidation();
  void loadServices();
});

const pasteHint = computed(() => {
  if (!service.value) return undefined;
  const filled = service.value.fields.filter((f) =>
    filledFields.value.includes(f.key),
  );
  return filled.length > 0
    ? t("notifications.channel-paste-filled", {
        fields: filled.map((field) => appriseFieldLabel(field, t)).join(", "),
      })
    : t("notifications.channel-paste-url-hint", {
        service: service.value.name,
      });
});

// A pasted URL, the service's own (a Discord webhook's) or an Apprise one, fills
// the form in; only the latest paste counts.
let pasteRequest = 0;

function clearPaste() {
  pasteRequest++;
  pastedUrl.value = "";
  pasteError.value = null;
  filling.value = false;
}

// Picking another service by hand leaves any pasted URL behind.
function pickKind(value: string) {
  kind.value = value;
  clearPaste();
}

async function fillFromUrl(url: string) {
  const request = ++pasteRequest;
  filling.value = true;
  pasteError.value = null;
  filledFields.value = [];
  try {
    const { data } = await notificationChannelApi.parseAppriseUrl(url);
    if (request !== pasteRequest) return;
    const found = services.value?.find((s) => s.id === data.service);
    if (!found) {
      pasteError.value = t("notifications.channel-paste-failed");
      return;
    }
    if (editing.value && found.id !== service.value?.id) {
      pasteError.value = t("notifications.channel-paste-other-service", {
        service: found.name,
      });
      return;
    }
    kind.value = `${APPRISE_PREFIX}${found.id}`;
    // Lets the service watcher start the form afresh before it's filled in.
    await nextTick();
    appriseValues.value = initialAppriseValues(found, data.fields);
    filledFields.value = found.fields
      .map((field) => field.key)
      .filter((key) => key in data.fields);
  } catch (err) {
    if (request !== pasteRequest) return;
    pasteError.value = errorMessage(
      err,
      t("notifications.channel-paste-failed"),
    );
  } finally {
    if (request === pasteRequest) filling.value = false;
  }
}

watchDebounced(
  pastedUrl,
  (url) => {
    if (url.trim()) void fillFromUrl(url.trim());
    else {
      pasteError.value = null;
      filledFields.value = [];
    }
  },
  { debounce: 400 },
);

function targetChanges(): NotificationChannelUpdatePayload {
  switch (type.value) {
    case "email":
      return { address: address.value.trim() };
    case "apprise":
      return service.value
        ? {
            fields: appriseFieldsPayload(
              service.value,
              appriseValues.value,
              removedSecrets.value,
            ),
          }
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

        <div :class="{ 'r-v2-channel-dialog__pair': !editing }">
          <RSelect
            v-if="!editing"
            :model-value="kind"
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
            @update:model-value="pickKind(String($event))"
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
            <RTextField
              v-model="pastedUrl"
              :label="t('notifications.channel-paste-url')"
              :hint="pasteHint"
              :error-messages="pasteError ?? undefined"
              :maxlength="NOTIFICATION_CHANNEL_URL_MAX_LENGTH"
              :loading="filling"
              autocomplete="off"
              prefix-label="stacked"
              mono
              @keydown.enter.prevent.stop
            />
            <AppriseServiceFields
              v-model="appriseValues"
              v-model:removed="removedSecrets"
              :service="service"
              :stored="storedSecrets"
              :highlighted="filledFields"
            />
            <RBtn
              v-if="service.setup_url"
              class="r-v2-channel-dialog__guide"
              variant="text"
              size="small"
              prepend-icon="mdi-open-in-new"
              :href="service.setup_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              {{
                t("notifications.channel-setup-guide", {
                  service: service.name,
                })
              }}
            </RBtn>
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

.r-v2-channel-dialog__guide {
  align-self: flex-start;
}
</style>
