<script setup lang="ts">
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import userApi from "@/services/api/user";
import type { Emitter } from "mitt";
import storeAuth from "@/stores/auth";
import { storeToRefs } from "pinia";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const heartbeatStore = storeHeartbeat();
const auth = storeAuth();
const { user } = storeToRefs(auth);
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const username = ref("");
const password = ref("");
const visiblePassword = ref(false);
const loggingIn = ref(false);
const loggingInOIDC = ref(false);
const {
  OIDC: { ENABLED: oidcEnabled, PROVIDER: oidcProvider },
  FRONTEND: { DISABLE_USERPASS_LOGIN: loginDisabled },
} = heartbeatStore.value;
const forgotMode = ref(false);
const forgotUser = ref("");
const sendingReset = ref(false);

// Functions
async function login() {
  loggingIn.value = true;

  await identityApi
    .login(username.value, password.value)
    .then(async () => {
      await refetchCSRFToken();
      try {
        const { data: userData } = await userApi.fetchCurrentUser();
        auth.setUser(userData);
      } catch (userError) {
        console.error("Error loading user: ", userError);
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

async function sendReset() {
  sendingReset.value = true;
  try {
    await identityApi.requestPasswordReset(forgotUser.value);
    emitter?.emit("snackbarShow", {
      msg: t("login.reset-sent"),
      icon: "mdi-check-circle",
      color: "green",
    });
    forgotMode.value = false;
    forgotUser.value = "";
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || error.message || "Error",
      icon: "mdi-alert-circle",
      color: "red",
    });
  } finally {
    sendingReset.value = false;
  }
}

async function loginOIDC() {
  loggingInOIDC.value = true;
  window.open("/api/login/openid", "_self");
}
</script>

<template>
  <v-card class="translucent-dark py-8 px-5" width="500">
    <v-img src="/assets/isotipo.svg" class="mx-auto mb-8" width="80" />
    <v-expand-transition>
      <v-row
        v-if="!forgotMode"
        class="text-white justify-center mt-2"
        no-gutters
      >
        <v-col cols="10">
          <v-form v-if="!loginDisabled" @submit.prevent="login">
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
              class="bg-toplayer mt-4"
              variant="text"
              block
              :loading="loggingIn"
              :disabled="loggingIn || !username || !password || loggingInOIDC"
            >
              <template #prepend>
                <v-icon>mdi-login</v-icon>
              </template>
              {{ t("login.login") }}
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
          <template v-if="oidcEnabled">
            <v-divider v-if="!loginDisabled" class="my-4">
              <template #default>
                <span class="px-1">{{ t("login.or") }}</span>
              </template>
            </v-divider>
            <v-btn
              block
              type="submit"
              class="bg-toplayer"
              variant="text"
              :disabled="loggingInOIDC || loggingIn"
              :loading="loggingInOIDC"
              @click="loginOIDC()"
            >
              <template v-if="oidcProvider" #prepend>
                <v-icon size="20">
                  <v-img
                    :src="`/assets/dashboard-icons/${oidcProvider
                      .toLowerCase()
                      .replace(/ /g, '-')}.png`"
                  >
                    <template #error>
                      <v-icon size="20">mdi-key</v-icon>
                    </template>
                  </v-img>
                </v-icon>
              </template>
              {{
                t("login.login-oidc", {
                  oidc: oidcProvider || "OIDC",
                })
              }}
              <template #loader>
                <v-progress-circular
                  color="primary"
                  :width="2"
                  :size="20"
                  indeterminate
                />
              </template>
            </v-btn>
          </template>
          <div v-if="!loginDisabled" class="my-6 text-right">
            <a
              class="text-blue text-caption"
              href="#"
              @click.prevent="forgotMode = true"
            >
              {{ t("login.forgot-password") }}
            </a>
          </div>
        </v-col>
      </v-row>
    </v-expand-transition>
    <v-expand-transition>
      <v-row
        v-if="forgotMode && !loginDisabled"
        class="text-white justify-center mt-2"
        no-gutters
      >
        <v-col cols="10">
          <v-form @submit.prevent="sendReset">
            <v-text-field
              v-model="forgotUser"
              :label="t('login.username')"
              type="text"
              required
              prepend-inner-icon="mdi-account"
              variant="underlined"
            />
            <v-btn
              type="submit"
              class="bg-toplayer mt-4"
              variant="text"
              block
              :loading="sendingReset"
              :disabled="sendingReset || !forgotUser"
            >
              <template #prepend>
                <v-icon>mdi-lock-reset</v-icon>
              </template>
              {{ t("login.send-reset-link") }}
              <template #loader>
                <v-progress-circular
                  color="primary"
                  :width="2"
                  :size="20"
                  indeterminate
                />
              </template>
            </v-btn>
            <v-btn
              variant="text"
              block
              class="mt-2"
              prepend-icon="mdi-chevron-left"
              @click="
                forgotMode = false;
                forgotUser = '';
              "
            >
              {{ t("common.cancel") }}
            </v-btn>
          </v-form>
        </v-col>
      </v-row>
    </v-expand-transition>
  </v-card>
</template>
