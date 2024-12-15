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
const apiKey = ref(auth.user?.ra_api_key);
const username = ref(auth.user?.ra_username);

watch(
  auth,
  (newAuth) => {
    apiKey.value = newAuth.user?.ra_api_key;
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
function editUser() {
  if (!auth.user) return;

  userApi
    .updateUser({
      id: auth.user.id,
      ra_api_key: apiKey.value as string,
      ra_username: username.value as string,
    })
    .then(() => {
      emitter?.emit("snackbarShow", {
        msg: `Updated RetroAchievements settings. Please Rescan`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 5000,
      });
    })
    .catch(() => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to update your  RetroAchievements settings.`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });
}
</script>

<template>
  <r-section icon="mdi-palette-swatch-outline" title="RetroAchievements">
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
      <v-form v-model="valid" @submit.prevent="editUser" class="pa-1">
        <v-row no-gutters>
          <v-col md="4">
            <v-text-field
              v-model="username"
              :counter="10"
              :rules="rules"
              label="Username"
              hide-details
              required
            />
          </v-col>

          <v-col md="4">
            <v-text-field
              v-model="apiKey"
              :rules="rules"
              label="Web Api Key"
              hide-details
              required
            />
          </v-col>
          <v-col class="d-flex">
            <v-btn type="submit" block height="100%">Submit</v-btn>
          </v-col>
        </v-row>
      </v-form>
    </template>
  </r-section>
</template>
