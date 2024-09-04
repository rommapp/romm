<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import { inject, ref } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import userApi from "@/services/api/user";

const valid = ref(false);
const username = ref("");
const apiKey = ref("");
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
console.log(auth.user);
const rules = [
  (value: string) => {
    if (value) return true;

    return "Field is required.";
  },
];
function editUser() {
  if (!auth.user) return;

  userApi
    .updateUserRetroAchievements({
      id: auth.user.id,
      ra_api_key: apiKey.value,
      ra_username: username.value,
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
        Explain what retro-achievements are and how to set it up
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
              :counter="10"
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
