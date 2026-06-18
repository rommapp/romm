<script setup lang="ts">
import { RBtn, RTextField } from "@v2/lib";
import { onBeforeMount, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import AuthBackLink from "@/v2/components/shared/AuthBackLink.vue";
import AuthCard from "@/v2/components/shared/AuthCard.vue";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const snackbar = useSnackbar();
const route = useRoute();
const router = useRouter();
const usersStore = storeUsers();
const token = route.query.token as string;

const username = ref("");
const email = ref("");
const password = ref("");
const submitting = ref(false);

async function register() {
  if (!username.value || !email.value || !password.value) return;
  submitting.value = true;
  try {
    await userApi.registerUser(
      username.value,
      email.value,
      password.value,
      token,
    );
    snackbar.success(t("login.register-success"), {
      icon: "mdi-check-circle",
      timeout: 5000,
    });
    router.push("/login");
  } catch (error: unknown) {
    const { response, message } = error as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      t("login.register-failed", {
        error: response?.data?.detail || message || "",
      }),
      { icon: "mdi-close-circle", timeout: 5000 },
    );
  } finally {
    submitting.value = false;
  }
}

// Redirect if no invite token is present.
onBeforeMount(() => {
  if (!token) router.push("/");
});
</script>

<template>
  <AuthCard>
    <form class="r-v2-register__form" @submit.prevent="register">
      <RTextField
        v-model="username"
        :label="t('settings.username')"
        type="text"
        variant="underlined"
        prepend-inner-icon="mdi-account"
        :rules="usersStore.usernameRules"
        autocomplete="username"
        :disabled="submitting"
      />
      <RTextField
        v-model="email"
        :label="t('settings.email')"
        type="email"
        variant="underlined"
        prepend-inner-icon="mdi-email"
        :rules="usersStore.emailRules"
        autocomplete="email"
        :disabled="submitting"
      />
      <PasswordField
        v-model="password"
        :label="t('settings.password')"
        autocomplete="new-password"
        :rules="usersStore.passwordRules"
        :disabled="submitting"
      />
      <RBtn
        type="submit"
        variant="flat"
        color="primary"
        block
        prepend-icon="mdi-account-check"
        :loading="submitting"
        :disabled="submitting || !username || !email || !password"
      >
        {{ t("common.create") }}
      </RBtn>
    </form>

    <AuthBackLink />
  </AuthCard>
</template>

<style scoped>
.r-v2-register__form {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
</style>
