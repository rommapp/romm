<script setup lang="ts">
// CreateUserDialog — create a user with profile fields plus access: an Admin
// toggle and, for non-admins, an initial permission group. Replaces the old
// role select (roles are superseded by admin-vs-user + groups).
import { RBtn, RIcon, RSelect, RSwitch, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import permissionsApi from "@/services/api/permissions";
import userApi from "@/services/api/user";
import storePermissionGroups from "@/stores/permissionGroups";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const usersStore = storeUsers();
const groupsStore = storePermissionGroups();
const snackbar = useSnackbar();

const show = ref(false);
const submitting = ref(false);

const user = ref({ username: "", password: "", email: "", role: "user" });
const confirmPassword = ref("");
const isAdmin = ref(false);
const groupId = ref<number | null>(null);

const groupItems = computed(() =>
  groupsStore.groups.map((g) => ({ title: g.name, value: g.id })),
);

const defaultGroupId = computed(() => groupsStore.defaultGroup?.id ?? null);

emitter?.on("showCreateUserDialog", async () => {
  reset();
  show.value = true;
  await groupsStore.ensureLoaded();
  // Pre-select the server default group so new users start where they land.
  groupId.value = defaultGroupId.value;
});

const confirmPasswordRules = computed(() => [
  (v: string) => !!v || t("settings.repeat-password-required"),
  (v: string) =>
    v === user.value.password || t("settings.passwords-must-match"),
]);

const formValid = computed(
  () =>
    user.value.username.trim().length >= 3 &&
    user.value.password.length >= 6 &&
    confirmPassword.value === user.value.password &&
    /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(user.value.email),
);

function reset() {
  user.value = { username: "", password: "", email: "", role: "user" };
  confirmPassword.value = "";
  isAdmin.value = false;
  groupId.value = null;
}

async function createUser() {
  if (!formValid.value) return;
  submitting.value = true;
  try {
    user.value.role = isAdmin.value ? "admin" : "user";
    const { data } = await userApi.createUser(user.value);
    // Only pin an explicit group when the admin picked a non-default one;
    // leaving the default selected lets the user follow the server default.
    if (
      !isAdmin.value &&
      groupId.value !== null &&
      groupId.value !== defaultGroupId.value
    ) {
      await permissionsApi.updateUserPermissions(data.id, {
        set_group: true,
        permission_group_id: groupId.value,
      });
      data.permission_group_id = groupId.value;
    }
    usersStore.add(data);
    snackbar.success(t("settings.user-created", { username: data.username }), {
      icon: "mdi-check-bold",
    });
    show.value = false;
    reset();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.unable-to-create-user", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}

function close() {
  show.value = false;
}
</script>

<template>
  <RDialog v-model="show" icon="mdi-account-plus" :width="540" @close="close">
    <template #header>
      <span class="r-v2-user-dialog__title">{{
        t("settings.create-user")
      }}</span>
    </template>
    <template #content>
      <RTextField
        v-model="user.username"
        prefix-label="stacked"
        :rules="usersStore.usernameRules"
        required
        clearable
      >
        <template #prefix-label>
          <RIcon icon="mdi-account-outline" size="14" />
          {{ t("settings.username") }}
        </template>
      </RTextField>
      <RTextField
        v-model="user.password"
        prefix-label="stacked"
        :rules="usersStore.passwordRules"
        type="password"
        autocomplete="new-password"
        required
        clearable
      >
        <template #prefix-label>
          <RIcon icon="mdi-key-outline" size="14" />
          {{ t("settings.password") }}
        </template>
      </RTextField>
      <RTextField
        v-model="confirmPassword"
        prefix-label="stacked"
        :rules="confirmPasswordRules"
        type="password"
        autocomplete="new-password"
        required
        clearable
      >
        <template #prefix-label>
          <RIcon icon="mdi-key-variant" size="14" />
          {{ t("settings.repeat-password") }}
        </template>
      </RTextField>
      <RTextField
        v-model="user.email"
        prefix-label="stacked"
        :rules="usersStore.emailRules"
        type="email"
        clearable
      >
        <template #prefix-label>
          <RIcon icon="mdi-email-outline" size="14" />
          {{ t("settings.email") }}
        </template>
      </RTextField>

      <div class="r-v2-user-dialog__admin">
        <RSwitch v-model="isAdmin" :label="t('settings.administrator')" />
        <span class="r-v2-user-dialog__hint">
          {{ t("settings.administrator-hint") }}
        </span>
      </div>
      <div v-if="!isAdmin" class="r-v2-user-dialog__field">
        <span class="r-v2-user-dialog__field-label">
          {{ t("settings.permission-group") }}
        </span>
        <RSelect
          v-model="groupId"
          variant="outlined"
          :items="groupItems"
          item-title="title"
          item-value="value"
          hide-details
        />
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        :disabled="!formValid"
        @click="createUser"
      >
        {{ t("common.create") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-user-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-user-dialog__admin {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.r-v2-user-dialog__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-user-dialog__field-label {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-user-dialog__hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
