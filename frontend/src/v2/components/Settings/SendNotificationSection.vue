<script setup lang="ts">
// SendNotificationSection: an admin notifies everyone, the admins or
// chosen users on demand, through the same endpoint API clients use.
import { RBtn, RForm, RIcon, RSelect, RTextField } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { NotificationLevel } from "@/__generated__";
import notificationApi from "@/services/api/notification";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { TONE_ICONS, useSnackbar } from "@/v2/composables/useSnackbar";
import {
  NOTIFICATION_BODY_MAX_LENGTH,
  NOTIFICATION_LINK_MAX_LENGTH,
  NOTIFICATION_TITLE_MAX_LENGTH,
  isInAppPath,
} from "@/v2/utils/notifications";
import { notBlank } from "@/v2/utils/validation";

defineOptions({ inheritAttrs: false });

type Audience = "all" | "admins" | "users";

const { t } = useI18n();
const snackbar = useSnackbar();
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);

const formRef = ref<InstanceType<typeof RForm> | null>(null);
const audience = ref<Audience>("all");
const userIds = ref<number[]>([]);
const level = ref<NotificationLevel>("info");
const title = ref("");
const body = ref("");
const link = ref("");
const sending = ref(false);

const AUDIENCE_ICONS: Record<Audience, string> = {
  all: "mdi-account-group-outline",
  admins: "mdi-shield-account-outline",
  users: "mdi-account-multiple-check-outline",
};

const audienceItems = computed(() =>
  (Object.keys(AUDIENCE_ICONS) as Audience[]).map((value) => ({
    title: t(`notifications.send-to-${value}`),
    value,
  })),
);

const levelItems = computed(() =>
  (Object.keys(TONE_ICONS) as NotificationLevel[]).map((value) => ({
    title: t(`notifications.level-${value}`),
    value,
  })),
);

const userItems = computed(() =>
  allUsers.value.map((user) => ({ title: user.username, value: user.id })),
);

const titleRules = [notBlank()];
const userRules = [
  (ids: number[]) => ids.length > 0 || t("notifications.send-users-required"),
];
const linkRules = [
  (value: string) =>
    !value.trim() ||
    isInAppPath(value.trim()) ||
    t("notifications.send-link-invalid"),
];

onMounted(async () => {
  if (allUsers.value.length > 0) return;
  try {
    const { data } = await userApi.fetchUsers();
    usersStore.set(data);
  } catch (error) {
    console.error("Could not load users:", error);
  }
});

async function send() {
  const result = await formRef.value?.validate();
  if (!result?.valid) return;
  sending.value = true;
  try {
    const { data } = await notificationApi.create({
      title: title.value.trim(),
      body: body.value.trim() || null,
      link: link.value.trim() || null,
      level: level.value,
      icon: "mdi-bullhorn-outline",
      recipients: audience.value === "users" ? userIds.value : audience.value,
    });
    snackbar.success(
      t("notifications.sent", data.length, { named: { n: data.length } }),
      { icon: "mdi-send-check-outline" },
    );
    title.value = "";
    body.value = "";
    link.value = "";
    formRef.value?.resetValidation();
  } catch (error) {
    console.error("Could not send notification:", error);
    snackbar.error(t("notifications.send-failed"));
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <SettingsSection
    :title="t('notifications.send-section')"
    icon="mdi-bullhorn-outline"
  >
    <!-- Enter mustn't send: an unfinished title would go out to everyone. -->
    <RForm ref="formRef" class="r-v2-send-notification" disable-enter-submit>
      <div class="r-v2-send-notification__pickers">
        <RSelect
          v-model="audience"
          :items="audienceItems"
          :prepend-inner-icon="AUDIENCE_ICONS[audience]"
          prefix-label="stacked"
          hide-details
        >
          <template #prefix-label>
            <RIcon icon="mdi-account-arrow-right-outline" size="14" />
            {{ t("notifications.send-recipients") }}
          </template>
        </RSelect>
        <RSelect
          v-model="level"
          :items="levelItems"
          :prepend-inner-icon="TONE_ICONS[level]"
          prefix-label="stacked"
          hide-details
        >
          <template #prefix-label>
            <RIcon icon="mdi-flag-outline" size="14" />
            {{ t("notifications.send-level") }}
          </template>
        </RSelect>
      </div>

      <RSelect
        v-if="audience === 'users'"
        v-model="userIds"
        :items="userItems"
        :rules="userRules"
        multiple
        chips
        searchable
        clearable
        prefix-label="stacked"
      >
        <template #prefix-label>
          <RIcon icon="mdi-account-multiple-outline" size="14" />
          {{ t("notifications.send-users") }}
        </template>
      </RSelect>

      <RTextField
        v-model="title"
        :rules="titleRules"
        :maxlength="NOTIFICATION_TITLE_MAX_LENGTH"
        prefix-label="stacked"
        required
      >
        <template #prefix-label>
          <RIcon icon="mdi-format-title" size="14" />
          {{ t("notifications.send-title") }}
        </template>
      </RTextField>

      <RTextField
        v-model="body"
        :maxlength="NOTIFICATION_BODY_MAX_LENGTH"
        multiline
        :rows="3"
        prefix-label="stacked"
      >
        <template #prefix-label>
          <RIcon icon="mdi-text" size="14" />
          {{ t("notifications.send-body") }}
        </template>
      </RTextField>

      <RTextField
        v-model="link"
        :rules="linkRules"
        :maxlength="NOTIFICATION_LINK_MAX_LENGTH"
        :hint="t('notifications.send-link-hint')"
        placeholder="/platforms"
        prefix-label="stacked"
        mono
      >
        <template #prefix-label>
          <RIcon icon="mdi-link-variant" size="14" />
          {{ t("notifications.send-link") }}
        </template>
      </RTextField>

      <div class="r-v2-send-notification__actions">
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-send-outline"
          class="r-v2-send-notification__send"
          :loading="sending"
          @click="send"
        >
          {{ t("notifications.send") }}
        </RBtn>
      </div>
    </RForm>
  </SettingsSection>
</template>

<style scoped>
.r-v2-send-notification {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
  padding: var(--r-space-4);
}

.r-v2-send-notification__pickers {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--r-space-3);
}

html[data-bp~="xs"] .r-v2-send-notification__pickers {
  grid-template-columns: minmax(0, 1fr);
}

.r-v2-send-notification__actions {
  display: flex;
  justify-content: flex-end;
}
</style>
