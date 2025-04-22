<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import { inject, ref } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import userApi from "@/services/api/user";
import { watch } from "vue";

const valid = ref(false);
const auth = storeAuth();
const username = ref(auth.user?.ra_username);
const visibleAPIKey = ref(false);

watch(
  auth,
  (newAuth) => {
    username.value = newAuth.user?.ra_username;
  },
  { deep: true },
);

const emitter = inject<Emitter<Events>>("emitter");
const rules = [
  (value: string) => {
    if (value) return true;

    return "Field is required.";
  },
];

// Functions
function refreshRetroAchievements() {
  if (!auth.user) return;

  userApi
    .refreshRetroAchievements({
      id: auth.user.id,
    })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `RetroAchievements profile synced`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 5000,
      });
    })
    .catch(() => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to sync your RetroAchievements profile.`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });
}
function submitRACredentials() {
  if (!auth.user) return;

  userApi
    .updateUser({
      id: auth.user.id,
      ra_username: username.value as string,
    })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `Updated RetroAchievements settings`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 5000,
      });
    })
    .catch(() => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to update your RetroAchievements settings.`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });

  // Refresh the RetroAchievements data
  refreshRetroAchievements();
}
</script>

<template>
  <r-section icon="mdi-trophy" title="RetroAchievements">
    <template #content>
      <p class="ma-4">
        Using your
        <a href="https://retroachievements.org/" target="_blank"
          >RetroAchievements</a
        >
        username and
        <a
          href="https://api-docs.retroachievements.org/getting-started.html#get-your-web-api-key"
          target="_blank"
          >API key</a
        >
        you can keep track of your latest achievements
      </p>
      <v-form
        v-model="valid"
        @submit.prevent="submitRACredentials"
        class="pa-1"
      >
        <v-row no-gutters>
          <v-col md="4" class="ma-2">
            <v-text-field
              v-model="username"
              :counter="10"
              :rules="rules"
              label="Username"
              variant="outlined"
              hide-details
              required
              prepend-inner-icon="mdi-account"
            />
          </v-col>
          <v-col class="ma-2">
            <v-btn type="submit" block class="h-100">Submit</v-btn>
          </v-col>
          <v-col v-if="auth.user?.ra_username" class="ma-2">
            <v-btn
              prepend-icon="mdi-sync"
              @click="refreshRetroAchievements"
              block
              class="h-100"
              >Sync</v-btn
            >
          </v-col>
        </v-row>
      </v-form>
    </template>
  </r-section>
</template>
