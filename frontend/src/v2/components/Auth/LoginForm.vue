<script setup lang="ts">
// LoginForm — username + password form. Emits `submit` on valid submission;
// the parent owns the API call + snackbars so this stays purely presentational.
import { RBtn, RTextField } from "@v2/lib";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { refetchCSRFToken } from "@/services/api";
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

defineProps<{
  blocking?: boolean;
}>();

const emit = defineEmits<{ (e: "forgot"): void }>();

const { t } = useI18n();
const router = useRouter();
const authStore = storeAuth();
const snackbar = useSnackbar();

const username = ref("");
const password = ref("");
const loggingIn = ref(false);

async function submit() {
  if (!username.value || !password.value) return;
  loggingIn.value = true;
  try {
    await identityApi.login(username.value, password.value);
    await refetchCSRFToken();
    try {
      await authStore.fetchCurrentUser();
    } catch (userError) {
      console.error("Error loading user: ", userError);
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
      t("login.login-failed");
    snackbar.error(t("login.unable-to-login", { error: errorMessage }), {
      icon: "mdi-close-circle",
    });
    console.error(
      `[${response?.status} ${response?.statusText}] ${errorMessage}`,
    );
  } finally {
    loggingIn.value = false;
  }
}

defineExpose({ loggingIn });
</script>

<template>
  <form class="r-v2-login-form" @submit.prevent="submit">
    <RTextField
      v-model="username"
      :label="t('login.username')"
      type="text"
      variant="underlined"
      autocomplete="username"
      name="username"
      prepend-inner-icon="mdi-account"
      :disabled="loggingIn"
    />
    <PasswordField
      v-model="password"
      :label="t('login.password')"
      name="password"
      :disabled="loggingIn"
    />
    <RBtn
      type="submit"
      variant="flat"
      color="primary"
      block
      prepend-icon="mdi-login"
      :loading="loggingIn"
      :disabled="loggingIn || blocking || !username || !password"
    >
      {{ t("login.login") }}
    </RBtn>

    <div class="r-v2-login-form__forgot">
      <a href="#" @click.prevent="emit('forgot')">
        {{ t("login.forgot-password") }}
      </a>
    </div>
  </form>
</template>

<style scoped>
.r-v2-login-form {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-v2-login-form__forgot {
  text-align: right;
  margin-top: var(--r-space-2);
}

.r-v2-login-form__forgot a {
  color: var(--r-color-brand-primary-hover);
  font-size: var(--r-font-size-sm);
  text-decoration: none;
  border-radius: var(--r-radius-sm);
}

.r-v2-login-form__forgot a:hover {
  text-decoration: underline;
}
</style>
