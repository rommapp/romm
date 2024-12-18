<script setup lang="ts">
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const username = ref("");
const password = ref("");
const visiblePassword = ref(false);
const loggingIn = ref(false);

// Functions
async function login() {
  loggingIn.value = true;

  await identityApi
    .login(username.value, password.value)
    .then(async () => {
      await refetchCSRFToken();
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
        msg: `Unable to login: ${errorMessage}`,
        icon: "mdi-close-circle",
        color: "red",
      });
      console.error(
        `[${response.status} ${response.statusText}] ${errorMessage}`,
      );
    })
    .finally(() => {
      loggingIn.value = false;
    });
}

async function loginOIDC() {
  loggingIn.value = true;
  window.open("/api/login/openid", "_self");
}
</script>

<template>
  <v-card class="translucent-dark py-8 px-5" width="500">
    <v-img src="/assets/isotipo.svg" class="mx-auto" width="150" />
    <v-row class="text-white justify-center mt-2" no-gutters>
      <v-col cols="10">
        <v-form @submit.prevent="login">
          <v-text-field
            v-model="username"
            :label="t('login.username')"
            type="text"
            required
            autocomplete="on"
            prepend-inner-icon="mdi-account"
            variant="underlined"
          />
          <v-text-field
            v-model="password"
            :label="t('login.password')"
            :type="visiblePassword ? 'text' : 'password'"
            required
            autocomplete="on"
            prepend-inner-icon="mdi-lock"
            :append-inner-icon="visiblePassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="visiblePassword = !visiblePassword"
            variant="underlined"
          />
          <v-btn
            type="submit"
            class="bg-terciary"
            block
            :loading="loggingIn"
            :disabled="loggingIn || !username || !password"
            :variant="!username || !password ? 'text' : 'flat'"
          >
            <span>{{ t("login.login") }}</span>
            <template #append>
              <v-icon class="text-romm-accent-1"
                >mdi-chevron-right-circle-outline</v-icon
              >
            </template>
            <template #loader>
              <v-progress-circular
                color="romm-accent-1"
                :width="2"
                :size="20"
                indeterminate
              />
            </template>
          </v-btn>
          <v-btn
            block
            type="submit"
            :disabled="loggingIn"
            v-if="heartbeatStore.value.OIDC.ENABLED"
            :loading="loggingIn"
            :variant="'text'"
            class="bg-terciary"
            @click="loginOIDC()"
          >
            <span>Login with OIDC</span>
            <template #append>
              <v-icon class="text-romm-accent-1"
                >mdi-chevron-right-circle-outline</v-icon
              >
            </template>
            <template #loader>
              <v-progress-circular
                color="romm-accent-1"
                :width="2"
                :size="20"
                indeterminate
              />
            </template>
          </v-btn>
        </v-form>
      </v-col>
    </v-row>
  </v-card>
</template>
