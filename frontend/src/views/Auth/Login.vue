<script setup lang="ts">
import identityApi from "@/services/api/identity";
import { refetchCSRFToken } from "@/services/api/index";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useRouter } from "vue-router";

// Props
const emitter = inject<Emitter<Events>>("emitter");
const router = useRouter();
const username = ref("");
const password = ref("");
const visiblePassword = ref(false);
const logging = ref(false);

// Functions
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
        `[${response.status} ${response.statusText}] ${errorMessage}`,
      );
    })
    .finally(() => {
      logging.value = false;
    });
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
            :append-inner-icon="visiblePassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="visiblePassword = !visiblePassword"
          />
          <v-btn
            type="submit"
            :disabled="logging || !username || !password"
            :variant="!username || !password ? 'text' : 'flat'"
            class="bg-terciary"
            block
            :loading="logging"
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
  </v-card>
</template>
