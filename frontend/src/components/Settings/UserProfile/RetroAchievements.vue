<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import storeAuth from "@/stores/auth";
import { inject, ref } from "vue";
import type { Emitter } from "mitt";
import type { Events } from "@/types/emitter";
import userApi from "@/services/api/user";
import { watch } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const valid = ref(false);
const auth = storeAuth();
const username = ref(auth.user?.ra_username);
const syncing = ref(false);
const emitter = inject<Emitter<Events>>("emitter");
const rules = [
  (value: string) => {
    if (value) return true;
    return "Field is required.";
  },
];

// Functions
async function refreshRetroAchievements() {
  if (!auth.user) return;

  syncing.value = true;

  await userApi
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
    })
    .finally(() => {
      syncing.value = false;
    });
}
async function submitRACredentials() {
  if (!auth.user) return;

  await userApi
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
      // Refresh the RetroAchievements data
      refreshRetroAchievements();
    })
    .catch(() => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to update your RetroAchievements settings.`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });
}
watch(
  auth,
  (newAuth) => {
    username.value = newAuth.user?.ra_username;
  },
  { deep: true },
);
</script>

<template>
  <r-section icon="mdi-trophy" title="RetroAchievements">
    <template #content>
      <v-form v-model="valid" @submit.prevent="submitRACredentials">
        <v-text-field
          v-model="username"
          :counter="10"
          :rules="rules"
          label="Username"
          variant="outlined"
          hide-details
          required
          prepend-inner-icon="mdi-account"
          class="ma-4"
        />
        <v-btn
          :disabled="syncing"
          :variant="syncing ? 'plain' : 'flat'"
          type="submit"
          class="ml-4 text-romm-green bg-toplayer"
          >{{ t("common.apply") }}</v-btn
        >
        <v-btn
          prepend-icon="mdi-sync"
          :disabled="syncing"
          :loading="syncing"
          class="ml-4 text-accent bg-toplayer"
          @click="refreshRetroAchievements"
        >
          <template #loader>
            <v-progress-circular
              color="accent"
              :width="2"
              :size="20"
              indeterminate
            />
          </template>
          {{ t("common.sync") }}
        </v-btn>
      </v-form>
    </template>
  </r-section>
</template>
