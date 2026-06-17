<script setup lang="ts">
// AuthBackLink — small right-aligned "← Back to login" link used by
// Register / ResetPassword / Setup. Points at `/login` by default;
// override via `to` for other destinations.
import { useI18n } from "vue-i18n";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    to?: string;
    label?: string;
  }>(),
  {
    to: "/login",
    label: undefined,
  },
);

const { t } = useI18n();
</script>

<template>
  <div class="auth-back">
    <a :href="to">{{ label ?? t("login.back-to-login") }}</a>
  </div>
</template>

<style scoped>
.auth-back {
  text-align: right;
}

.auth-back a {
  color: var(--r-color-brand-primary-hover);
  font-size: var(--r-font-size-sm);
  text-decoration: none;
}

.auth-back a:hover {
  text-decoration: underline;
}
</style>
