<script setup lang="ts">
// RetroAchievementsSection — links a RomM account to a RetroAchievements
// profile and triggers a re-sync. Single primary button does both:
// updates the username on the user record AND kicks off a sync of the
// linked profile (full sync after a username change, incremental
// otherwise). Listens to `auth.user?.ra_username` so the connection
// state chip stays accurate.
import { RBtn, RTag, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const auth = storeAuth();
const snackbar = useSnackbar();

const username = ref(auth.user?.ra_username ?? "");
const submitting = ref(false);

watch(
  () => auth.user?.ra_username,
  (next) => {
    username.value = next ?? "";
  },
);

const linkedUsername = computed(() => auth.user?.ra_username ?? "");
const isLinked = computed(() => linkedUsername.value.length > 0);
const isDirty = computed(() => username.value.trim() !== linkedUsername.value);
const canSubmit = computed(
  () => !submitting.value && (isDirty.value || isLinked.value),
);

async function syncProfile(incremental: boolean) {
  if (!auth.user) return;
  await userApi.refreshRetroAchievements({
    id: auth.user.id,
    incremental,
  });
}

async function saveAndSync() {
  if (!auth.user) return;
  submitting.value = true;
  const trimmed = username.value.trim();
  const usernameChanged = trimmed !== linkedUsername.value;

  try {
    if (usernameChanged) {
      await userApi.updateUser({
        id: auth.user.id,
        ra_username: trimmed,
      });
    }
    // Username change → full sync; same username → incremental refresh.
    await syncProfile(!usernameChanged);
    snackbar.success(
      usernameChanged
        ? t("settings.ra-saved-and-synced")
        : t("settings.ra-saved-and-synced"),
      { icon: "mdi-check-bold" },
    );
  } catch (err) {
    console.error(err);
    snackbar.error(
      usernameChanged
        ? t("settings.ra-update-failed")
        : t("settings.ra-sync-failed"),
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <SettingsSection :title="t('settings.retroachievements')" icon="mdi-trophy">
    <template #header-actions>
      <RTag
        :icon="isLinked ? 'mdi-link-variant' : 'mdi-link-variant-off'"
        :tone="isLinked ? 'success' : 'neutral'"
        size="small"
      >
        {{
          isLinked
            ? t("settings.ra-connected", { username: `@${linkedUsername}` })
            : t("settings.ra-not-linked")
        }}
      </RTag>
    </template>
    <div class="r-v2-ra__field">
      <RTextField
        v-model="username"
        prefix-label="stacked"
        hide-details
        @keyup.enter="saveAndSync"
      >
        <template #prefix-label>{{ t("settings.username") }}</template>
      </RTextField>
    </div>
    <div class="r-v2-ra__actions">
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        :disabled="!canSubmit || !username.trim()"
        :prepend-icon="isDirty ? 'mdi-link-variant' : 'mdi-sync'"
        @click="saveAndSync"
      >
        {{ isDirty ? t("common.save") : t("common.sync") }}
      </RBtn>
    </div>
  </SettingsSection>
</template>

<style scoped>
.r-v2-ra__field {
  padding: 14px 16px;
}

.r-v2-ra__actions {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid var(--r-color-border);
}
</style>
