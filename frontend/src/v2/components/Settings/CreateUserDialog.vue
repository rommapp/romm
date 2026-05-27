<script setup lang="ts">
// CreateUserDialog — v2-native rebuild of v1
// `Settings/Administration/Users/Dialog/CreateUser.vue`. Single dialog
// with username + password + email + role select; validates against
// the existing `usersStore` rule arrays.
import { RBtn, RIcon, RSelect, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import { getRoleIcon } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const usersStore = storeUsers();
const snackbar = useSnackbar();

const show = ref(false);
const submitting = ref(false);

const user = ref({
  username: "",
  password: "",
  email: "",
  role: "viewer",
});
const confirmPassword = ref("");

emitter?.on("showCreateUserDialog", () => {
  reset();
  show.value = true;
});

const roleItems = computed(() =>
  ["viewer", "editor", "admin"].map((role) => ({
    title: t(`settings.role-${role}`),
    value: role,
  })),
);

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
  user.value = { username: "", password: "", email: "", role: "viewer" };
  confirmPassword.value = "";
}

async function createUser() {
  if (!formValid.value) return;
  submitting.value = true;
  try {
    const { data } = await userApi.createUser(user.value);
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
      <RSelect
        v-model="user.role"
        variant="outlined"
        :items="roleItems"
        :label="t('settings.role')"
        required
        hide-details
      >
        <template #selection="{ item }">
          <div class="r-v2-user-dialog__role-line">
            <RIcon :icon="getRoleIcon(item.value)" size="16" />
            {{ item.title }}
          </div>
        </template>
        <template #item="{ props: itemProps, item }">
          <li v-bind="itemProps">
            <RIcon :icon="getRoleIcon(item.value)" size="16" />
            <span class="r-select__item-title">{{ item.title }}</span>
          </li>
        </template>
      </RSelect>
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
.r-v2-user-dialog__role-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}
</style>
