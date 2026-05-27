<script setup lang="ts">
// ResetForm — username-only form that triggers a password-reset email.
// Emits `done` on success and `cancel` when the user backs out.
import { RBtn, RTextField } from "@v2/lib";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import identityApi from "@/services/api/identity";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const emit = defineEmits<{
  (e: "done"): void;
  (e: "cancel"): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();

const forgotUser = ref("");
const sending = ref(false);

async function submit() {
  if (!forgotUser.value) return;
  sending.value = true;
  try {
    await identityApi.requestPasswordReset(forgotUser.value);
    snackbar.success(t("login.reset-sent"), { icon: "mdi-check-circle" });
    forgotUser.value = "";
    emit("done");
  } catch (error) {
    console.error("Error sending reset link: ", error);
    snackbar.error(t("login.reset-link-failed"), { icon: "mdi-alert-circle" });
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <form class="r-v2-reset-form" @submit.prevent="submit">
    <RTextField
      v-model="forgotUser"
      :label="t('login.username')"
      type="text"
      variant="underlined"
      prepend-inner-icon="mdi-account"
      :disabled="sending"
    />
    <RBtn
      type="submit"
      variant="flat"
      color="primary"
      block
      prepend-icon="mdi-lock-reset"
      :loading="sending"
      :disabled="sending || !forgotUser"
    >
      {{ t("login.send-reset-link") }}
    </RBtn>
    <RBtn
      variant="text"
      block
      prepend-icon="mdi-chevron-left"
      @click="
        forgotUser = '';
        emit('cancel');
      "
    >
      {{ t("common.cancel") }}
    </RBtn>
  </form>
</template>

<style scoped>
.r-v2-reset-form {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}
</style>
