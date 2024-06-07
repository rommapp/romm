<script setup lang="ts">
import identityApi from "@/services/api/identity";
import storeAuth from "@/stores/auth";
import storeHeartbeat from "@/stores/heartbeat";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, onBeforeMount, ref } from "vue";
import { useRouter } from "vue-router";

// Props
const heartbeatStore = storeHeartbeat();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const username = ref();
const password = ref();
const visiblePassword = ref(false);
const logging = ref(false);

function login() {
  logging.value = true;
  identityApi
    .login(username.value, password.value)
    .then(() => {
      const next = (router.currentRoute.value.query?.next || "/").toString();
      router.push(next);
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

onBeforeMount(async () => {
  // Check if authentication is enabled
  if (!auth.enabled) {
    return router.push({ name: "dashboard" });
  }
});
</script>

<template>
  <span id="bg" />

  <v-container class="fill-height justify-center">
    <v-card
      id="card"
      class="py-8 px-5"
      width="500"
    >
      <v-row>
        <v-col>
          <v-img
            src="/assets/isotipo.svg"
            class="mx-auto"
            width="200"
            height="200"
          />

          <v-row class="text-white justify-center mt-2">
            <v-col
              cols="10"
              md="8"
            >
              <v-text-field
                v-model="username"
                prepend-inner-icon="mdi-account"
                type="text"
                label="Username"
                variant="underlined"
                @keyup.enter="login()"
              />
              <v-text-field
                v-model="password"
                prepend-inner-icon="mdi-lock"
                :type="visiblePassword ? 'text' : 'password'"
                label="Password"
                variant="underlined"
                :append-inner-icon="visiblePassword ? 'mdi-eye-off' : 'mdi-eye'"
                @keyup.enter="login()"
                @click:append-inner="visiblePassword = !visiblePassword"
              />
            </v-col>
          </v-row>

          <v-row class="justify-center">
            <v-col
              cols="10"
              md="8"
            >
              <v-btn
                :disabled="logging"
                color="romm-accent-1"
                append-icon="mdi-chevron-right-circle-outline"
                block
                :loading="logging"
                @click="login()"
              >
                Login
                <template #loader>
                  <v-progress-circular
                    color="romm-accent-1"
                    :width="2"
                    :size="20"
                    indeterminate
                  />
                </template>
              </v-btn>
            </v-col>
          </v-row>
        </v-col>
      </v-row>
    </v-card>

    <div
      id="version"
      class="position-absolute"
    >
      <span class="text-white">{{ heartbeatStore.value.VERSION }}</span>
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
#card {
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(10px);
}
#version {
  text-shadow: 1px 1px 1px #000000, 0 0 1px #000000;
  bottom: 0.3rem;
  right: 0.5rem;
}
</style>
