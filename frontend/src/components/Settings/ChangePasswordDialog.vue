<script setup lang="ts">
// ChangePasswordDialog: new + confirm fields with matching validation, plus
// the current password when the account has one (the backend requires it).
//
// Mounted by UserProfile via local `v-model:open` (no emitter event)
// because nothing else in the app needs to trigger this dialog.
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import PasswordField from "@/components/shared/PasswordField.vue";
import { useSnackbar } from "@/composables/useSnackbar";
import { RBtn, RIcon } from "@/lib";
import RDialog from "@/lib/overlays/RDialog/RDialog.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { errorMessage } from "@/utils/errorMessage";

defineOptions({ inheritAttrs: false });

interface Props {
  open: boolean;
  /** User id whose password is being changed. */
  userId: number | null | undefined;
}
const props = defineProps<Props>();

const emit = defineEmits<{
  (e: "update:open", value: boolean): void;
}>();

const { t } = useI18n();
const auth = storeAuth();
const snackbar = useSnackbar();

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const submitting = ref(false);

watch(
  () => props.open,
  (open) => {
    if (open) {
      currentPassword.value = "";
      newPassword.value = "";
      confirmPassword.value = "";
    }
  },
);

// An account without a password (OIDC-provisioned) sets its first one.
const requiresCurrentPassword = computed(
  () => props.userId === auth.user?.id && !!auth.user?.has_password,
);

const passwordsMatch = computed(
  () =>
    confirmPassword.value.length === 0 ||
    confirmPassword.value === newPassword.value,
);

const passwordValid = computed(
  () => newPassword.value.length >= 6 && newPassword.value.length <= 255,
);

const canSubmit = computed(
  () =>
    passwordValid.value &&
    (!requiresCurrentPassword.value || currentPassword.value.length > 0) &&
    confirmPassword.value.length > 0 &&
    passwordsMatch.value &&
    !submitting.value,
);

const required = (v: string) => !!v || t("common.required");

const currentPasswordRules = [required];

const newPasswordRules = [
  required,
  (v: string) =>
    (v.length >= 6 && v.length <= 255) || t("common.password-length"),
];

const confirmRules = computed(() => [
  (v: string) => !!v || t("settings.repeat-password-required"),
  (v: string) => v === newPassword.value || t("settings.passwords-must-match"),
]);

function close() {
  emit("update:open", false);
}

async function submit() {
  if (!props.userId || !canSubmit.value) return;
  submitting.value = true;
  try {
    const { data } = await userApi.updateUser({
      id: props.userId,
      password: newPassword.value,
      current_password: requiresCurrentPassword.value
        ? currentPassword.value
        : undefined,
    });
    if (data.id === auth.user?.id) auth.setCurrentUser(data);
    snackbar.success(t("settings.password-updated"), {
      icon: "mdi-check-bold",
    });
    close();
  } catch (err) {
    snackbar.error(
      t("settings.unable-to-update-password", { detail: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <RDialog
    :model-value="open"
    icon="mdi-key-variant"
    :width="480"
    cancelable
    @update:model-value="(v) => emit('update:open', v)"
    @close="close"
  >
    <template #header>
      <span class="r-pwd-dialog__title">
        {{ t("settings.change-password") }}
      </span>
    </template>
    <template #content>
      <PasswordField
        v-if="requiresCurrentPassword"
        v-model="currentPassword"
        prefix-label="stacked"
        :rules="currentPasswordRules"
        :prepend-inner-icon="undefined"
        autocomplete="current-password"
        required
        @keyup.enter="submit"
      >
        <template #prefix-label>
          <RIcon icon="mdi-lock-outline" size="14" />
          {{ t("settings.current-password") }}
        </template>
      </PasswordField>
      <PasswordField
        v-model="newPassword"
        prefix-label="stacked"
        :rules="newPasswordRules"
        :prepend-inner-icon="undefined"
        autocomplete="new-password"
        required
        @keyup.enter="submit"
      >
        <template #prefix-label>
          <RIcon icon="mdi-key-plus" size="14" />
          {{ t("settings.new-password") }}
        </template>
      </PasswordField>
      <PasswordField
        v-model="confirmPassword"
        prefix-label="stacked"
        :rules="confirmRules"
        :prepend-inner-icon="undefined"
        autocomplete="new-password"
        required
        @keyup.enter="submit"
      >
        <template #prefix-label>
          <RIcon icon="mdi-key-variant" size="14" />
          {{ t("settings.repeat-password") }}
        </template>
      </PasswordField>
      <p class="r-pwd-dialog__hint">
        <RIcon icon="mdi-information-outline" size="14" />
        <span>{{ t("common.password-length") }}</span>
      </p>
    </template>
    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        prepend-icon="mdi-check"
        @click="submit"
      >
        {{ t("common.confirm") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-pwd-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-pwd-dialog__hint {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}
</style>
