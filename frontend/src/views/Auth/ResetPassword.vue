<script setup lang="ts">
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import type { Events } from "@/types/emitter";
import userApi from "@/services/api/user";
import type { Emitter } from "mitt";
import storeAuth from "@/stores/auth";
import { inject, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const router = useRouter();
const token = route.query.token as string;
const newPassword = ref("");
const confirmPassword = ref("");
const visibleNewPassword = ref(false);
const visibleConfirmNewPassword = ref(false);

// Functions
async function resetPassword() {
  await identityApi
    .resetPassword(token, newPassword.value)
    .then(async () => {
      await refetchCSRFToken();
      try {
        const { data: userData } = await userApi.fetchCurrentUser();
        auth.setUser(userData);
      } catch (error) {
        console.error("Error setting a new password: ", error);
      }
      const params = new URLSearchParams(window.location.search);
      router.push(params.get("next") ?? "/");
    })
    .catch(({ response, message }) => {
      const errorMessage =
        response.data?.detail ||
        response.data ||
        message ||
        response.statusText;
      emitter?.emit("snackbarShow", {
        msg: `Unable to reset password: ${errorMessage}`,
        icon: "mdi-close-circle",
        color: "red",
      });
      console.error(
        `[${response.status} ${response.statusText}] ${errorMessage}`,
      );
    });
}
</script>

<template>
  <v-card class="translucent-dark py-8 px-5" width="500">
    <v-img src="/assets/isotipo.svg" class="mx-auto mb-8" width="80" />
    <v-row class="text-white justify-center mt-2" no-gutters>
      <v-col cols="10">
        <v-form @submit.prevent="resetPassword">
          <v-text-field
            v-model="newPassword"
            :label="t('login.new-password')"
            :type="visibleNewPassword ? 'text' : 'password'"
            required
            :append-inner-icon="visibleNewPassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="visibleNewPassword = !visibleNewPassword"
            variant="underlined"
          />
          <v-text-field
            v-model="confirmPassword"
            :label="t('login.confirm-new-password')"
            :type="visibleConfirmNewPassword ? 'text' : 'password'"
            required
            :append-inner-icon="
              visibleConfirmNewPassword ? 'mdi-eye-off' : 'mdi-eye'
            "
            @click:append-inner="
              visibleConfirmNewPassword = !visibleConfirmNewPassword
            "
            variant="underlined"
          />
          <span
            class="text-red text-caption"
            v-if="newPassword !== confirmPassword && newPassword.length > 0"
            >Passwords do not match</span
          >
          <v-btn
            type="submit"
            class="bg-toplayer mt-4"
            variant="text"
            block
            :disabled="newPassword !== confirmPassword"
          >
            <template #prepend>
              <v-icon>mdi-send</v-icon>
            </template>
            {{ t("login.reset-password") }}
            <template #loader>
              <v-progress-circular
                color="primary"
                :width="2"
                :size="20"
                indeterminate
              />
            </template>
          </v-btn>
        </v-form>
        <div class="my-6 text-right">
          <a class="text-blue text-caption" href="/login">
            {{ t("login.back-to-login") }}
          </a>
        </div>
      </v-col>
    </v-row>
  </v-card>
</template>
