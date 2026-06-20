<script setup lang="ts">
import { RAlert, RBtn } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { refetchCSRFToken } from "@/services/api";
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import AuthBackLink from "@/v2/components/shared/AuthBackLink.vue";
import AuthCard from "@/v2/components/shared/AuthCard.vue";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const authStore = storeAuth();
const snackbar = useSnackbar();
const route = useRoute();
const router = useRouter();
const token = route.query.token as string;

const newPassword = ref("");
const confirmPassword = ref("");
const submitting = ref(false);

const passwordsMismatch = computed(
  () =>
    newPassword.value.length > 0 && newPassword.value !== confirmPassword.value,
);

async function resetPassword() {
  if (passwordsMismatch.value || !newPassword.value) return;
  submitting.value = true;
  try {
    await identityApi.resetPassword(token, newPassword.value);
    await refetchCSRFToken();
    try {
      await authStore.fetchCurrentUser();
    } catch (error) {
      console.error("Error setting a new password: ", error);
    }
    const params = new URLSearchParams(window.location.search);
    router.push(params.get("next") ?? "/");
  } catch (err: unknown) {
    const { response, message } = err as {
      response?: {
        data?: { detail?: string };
        statusText?: string;
        status?: number;
      };
      message?: string;
    };
    const errorMessage =
      response?.data?.detail ||
      message ||
      response?.statusText ||
      t("login.reset-failed");
    snackbar.error(
      t("login.unable-to-reset-password", { error: errorMessage }),
      {
        icon: "mdi-close-circle",
      },
    );
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <AuthCard>
    <form class="r-v2-reset__form" @submit.prevent="resetPassword">
      <PasswordField
        v-model="newPassword"
        :label="t('login.new-password')"
        autocomplete="new-password"
        :disabled="submitting"
      />
      <PasswordField
        v-model="confirmPassword"
        :label="t('login.confirm-new-password')"
        prepend-inner-icon="mdi-lock-check"
        autocomplete="new-password"
        :disabled="submitting"
      />

      <RAlert
        v-if="passwordsMismatch"
        type="error"
        density="compact"
        :text="t('login.passwords-do-not-match')"
      />

      <RBtn
        type="submit"
        variant="flat"
        color="primary"
        block
        prepend-icon="mdi-send"
        :loading="submitting"
        :disabled="
          submitting || passwordsMismatch || !newPassword || !confirmPassword
        "
      >
        {{ t("login.reset-password") }}
      </RBtn>
    </form>

    <AuthBackLink />
  </AuthCard>
</template>

<style scoped>
.r-v2-reset__form {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
</style>
