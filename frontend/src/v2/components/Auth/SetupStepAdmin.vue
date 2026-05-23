<script setup lang="ts">
// SetupStepAdmin — Step 2 of the setup wizard. Creates the first admin
// account that owns the library and manages other users.
//
// The wizard owns the form draft (Setup.vue keeps the state so navigating
// to Step 1 and back preserves what the user typed). This component is
// pure UI: bind props in, emit input/validity out.
import { RForm, RTextField } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import PasswordField from "@/v2/components/shared/PasswordField.vue";
import {
  asciiOnly,
  email as emailRule,
  passwordLength,
  required,
  usernameChars,
  usernameLength,
} from "@/v2/utils/validation";

export interface AdminUserDraft {
  username: string;
  email: string;
  password: string;
  repeatPassword: string;
}

defineOptions({ inheritAttrs: false });

const draft = defineModel<AdminUserDraft>({ required: true });
const valid = defineModel<boolean>("valid", { default: false });

const emit = defineEmits<{ (e: "submit"): void }>();

const { t } = useI18n();

const usernameRules = [required(), usernameLength, usernameChars, asciiOnly];
const emailRules = computed(() => {
  if (!draft.value.email) return [];
  return [emailRule];
});
const passwordRules = [required(), passwordLength];
const repeatPasswordRules = computed(() => [
  required(t("settings.repeat-password-required")),
  (v: string) =>
    v === draft.value.password || t("settings.passwords-must-match"),
]);
</script>

<template>
  <div class="r-setup-admin">
    <p class="r-setup-admin__lead">
      {{ t("setup.admin-user-intro") }}
    </p>
    <RForm v-model="valid" class="r-setup-admin__form" @submit="emit('submit')">
      <RTextField
        :model-value="draft.username"
        :label="t('settings.username')"
        type="text"
        variant="underlined"
        autocomplete="username"
        prepend-inner-icon="mdi-account"
        :rules="usernameRules"
        @update:model-value="(v: string) => (draft.username = v)"
      />
      <RTextField
        :model-value="draft.email"
        :label="t('settings.email')"
        type="email"
        variant="underlined"
        autocomplete="email"
        prepend-inner-icon="mdi-email"
        :rules="emailRules"
        @update:model-value="(v: string) => (draft.email = v)"
      />
      <PasswordField
        :model-value="draft.password"
        :label="t('settings.password')"
        autocomplete="new-password"
        :rules="passwordRules"
        @update:model-value="(v: string) => (draft.password = v)"
      />
      <PasswordField
        :model-value="draft.repeatPassword"
        :label="t('settings.repeat-password')"
        autocomplete="new-password"
        :rules="repeatPasswordRules"
        @update:model-value="(v: string) => (draft.repeatPassword = v)"
      />
    </RForm>
  </div>
</template>

<style scoped>
.r-setup-admin {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--r-space-5);
}

.r-setup-admin__lead {
  margin: 0;
  max-width: 520px;
  text-align: center;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-setup-admin__form {
  width: 100%;
  max-width: 440px;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
</style>
