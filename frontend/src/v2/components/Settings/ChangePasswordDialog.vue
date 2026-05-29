<script setup lang="ts">
// ChangePasswordDialog — replaces the inline password field that lived
// in v1's UserProfile form. Two fields (new + confirm) with matching
// validation; the API call is `userApi.updateUser({ id, password })`.
//
// Mounted by UserProfile via local `v-model:open` (no emitter event)
// because nothing else in the app needs to trigger this dialog.
import { RBtn, RIcon } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

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

const newPassword = ref("");
const confirmPassword = ref("");
const submitting = ref(false);

watch(
  () => props.open,
  (open) => {
    if (open) {
      newPassword.value = "";
      confirmPassword.value = "";
    }
  },
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
    confirmPassword.value.length > 0 &&
    passwordsMatch.value &&
    !submitting.value,
);

const newPasswordRules = [
  (v: string) => !!v || t("common.required"),
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
    });
    if (data.id === auth.user?.id) auth.setCurrentUser(data);
    snackbar.success(t("settings.password-updated"), {
      icon: "mdi-check-bold",
    });
    close();
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `${t("settings.password-updated")}: ${
        e?.response?.data?.detail || e?.response?.statusText || e?.message
      }`,
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
    @update:model-value="(v) => emit('update:open', v)"
    @close="close"
  >
    <template #header>
      <span class="r-v2-pwd-dialog__title">
        {{ t("settings.change-password") }}
      </span>
    </template>
    <template #content>
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
      <p class="r-v2-pwd-dialog__hint">
        <RIcon icon="mdi-information-outline" size="14" />
        <span>{{ t("common.password-length") }}</span>
      </p>
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
.r-v2-pwd-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-pwd-dialog__hint {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}
</style>
