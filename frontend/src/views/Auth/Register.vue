<script setup lang="ts">
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import userApi from "@/services/api/user";
import { inject, ref, onBeforeMount } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const route = useRoute();
const router = useRouter();
const token = route.query.token as string;
const username = ref("");
const email = ref("");
const password = ref("");
const visiblePassword = ref(false);

// Functions
function register() {
  userApi
    .registerUser(username.value, email.value, password.value, token)
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: "User registered successfully",
        icon: "mdi-check-circle",
        color: "green",
        timeout: 5000,
      });
      router.push("/login");
    })
    .catch((error) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to register user: ${
          error?.response?.data?.detail || error?.message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });
}
// Redirect to login if no token is not valid
onBeforeMount(() => {
  if (!token) {
    router.push("/");
  }
});
</script>

<template>
  <v-card class="translucent-dark py-8 px-5" width="500">
    <v-img src="/assets/isotipo.svg" class="mx-auto mb-8" width="80" />
    <v-row class="text-white justify-center mt-2" no-gutters>
      <v-col cols="10">
        <v-form @submit.prevent="register">
          <v-text-field
            v-model="username"
            :label="t('settings.username')"
            type="text"
            required
            hide-details
            variant="underlined"
            class="mt-4"
          />
          <v-text-field
            v-model="email"
            :label="t('settings.email')"
            type="text"
            required
            hide-details
            variant="underlined"
            class="mt-4"
          />
          <v-text-field
            v-model="password"
            :label="t('settings.password')"
            :type="visiblePassword ? 'text' : 'password'"
            required
            :append-inner-icon="visiblePassword ? 'mdi-eye-off' : 'mdi-eye'"
            @click:append-inner="visiblePassword = !visiblePassword"
            variant="underlined"
            class="mt-4"
          />
          <v-btn type="submit" class="bg-toplayer mt-4" variant="text" block>
            <template #prepend>
              <v-icon>mdi-account-check</v-icon>
            </template>
            {{ t("common.create") }}
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
