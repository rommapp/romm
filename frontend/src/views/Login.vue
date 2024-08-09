<script setup lang="ts">
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";

// Props
const heartbeatStore = storeHeartbeat();
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const username = ref("");
const password = ref("");
const visiblePassword = ref(false);
const logging = ref(false);

async function login() {
  logging.value = true;

  await identityApi
    .login(username.value, password.value)
    .then(async () => {
      // Refetch CSRF token
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
        `[${response.status} ${response.statusText}] ${errorMessage}`
      );
    })
    .finally(() => {
      logging.value = false;
    });
}
</script>

<template>
  <span id="bg" />

  <v-container class="fill-height justify-center">
    <v-card class="translucent-dark py-8 px-5" width="500">
      <v-row no-gutters>
        <v-col>
          <v-img src="/assets/isotipo.svg" class="mx-auto" width="150" />

          <v-row class="text-white justify-center mt-2" no-gutters>
            <v-col cols="10" md="8">
              <v-form @submit.prevent>
                <v-text-field
                  v-model="username"
                  autocomplete="on"
                  required
                  prepend-inner-icon="mdi-account"
                  type="text"
                  label="Username"
                  variant="underlined"
                />
                <v-text-field
                  v-model="password"
                  autocomplete="on"
                  required
                  prepend-inner-icon="mdi-lock"
                  :type="visiblePassword ? 'text' : 'password'"
                  label="Password"
                  variant="underlined"
                  :append-inner-icon="
                    visiblePassword ? 'mdi-eye-off' : 'mdi-eye'
                  "
                  @click:append-inner="visiblePassword = !visiblePassword"
                />
                <v-btn
                  type="submit"
                  :disabled="logging || !username || !password"
                  :variant="!username || !password ? 'text' : 'flat'"
                  class="bg-terciary"
                  block
                  :loading="logging"
                  @click="login()"
                >
                  <span>Login</span>
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
        </v-col>
      </v-row>
    </v-card>

    <div id="version" class="position-absolute">
      <span class="text-white text-shadow">{{ heartbeatStore.value.VERSION }}</span>
    </div>
  </v-container>
</template>

<style>
#bg {
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  position: absolute;
  background: url("/assets/login_bg.png") center center;
  background-size: cover;
}
#version {
  bottom: 0.3rem;
  right: 0.5rem;
}
</style>
