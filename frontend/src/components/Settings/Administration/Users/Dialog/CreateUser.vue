<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import { getRoleIcon } from "@/utils";

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateUserDialog", () => {
  show.value = true;
});
const { t } = useI18n();
const user = ref({
  username: "",
  password: "",
  email: "",
  role: "viewer",
});
const { lgAndUp } = useDisplay();
const show = ref(false);
const usersStore = storeUsers();
const validForm = ref(false);

async function createUser() {
  await userApi
    .createUser(user.value)
    .then(({ data }) => {
      usersStore.add(data);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to create user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });
  show.value = false;
}

function closeDialog() {
  show.value = false;
  user.value = {
    username: "",
    password: "",
    email: "",
    role: "viewer",
  };
}
</script>
<template>
  <RDialog
    v-model="show"
    icon="mdi-account"
    :width="lgAndUp ? '60vw' : '95vw'"
    @close="closeDialog"
  >
    <template #content>
      <v-form v-model="validForm">
        <v-row no-gutters class="pa-4">
          <v-col>
            <v-text-field
              v-model="user.username"
              variant="outlined"
              :label="t('settings.username')"
              :rules="usersStore.usernameRules"
              required
              clearable
              class="ma-2"
            />
            <v-text-field
              v-model="user.password"
              variant="outlined"
              :label="t('settings.password')"
              :rules="usersStore.passwordRules"
              type="password"
              required
              clearable
              class="ma-2"
            />
            <v-text-field
              v-model="user.email"
              variant="outlined"
              :label="t('settings.email')"
              :rules="usersStore.emailRules"
              type="email"
              clearable
              class="ma-2"
            />
            <v-select
              v-model="user.role"
              variant="outlined"
              :items="['viewer', 'editor', 'admin']"
              :label="t('settings.role')"
              required
              hide-details
              class="ma-2"
            >
              <template #selection="{ item }">
                <v-list-item class="pa-0">
                  <v-icon class="mr-2">
                    {{ getRoleIcon(item.title) }}
                  </v-icon>
                  {{ item.title }}
                </v-list-item>
              </template>
              <template #item="{ item, props }">
                <v-list-item v-bind="props" :title="item.title">
                  <template #prepend>
                    <v-icon>{{ getRoleIcon(item.title) }}</v-icon>
                  </template>
                </v-list-item>
              </template>
            </v-select>
          </v-col>
        </v-row>
      </v-form>
    </template>
    <template #append>
      <v-divider />
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-toplayer" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            :variant="!validForm ? 'plain' : 'flat'"
            :disabled="!validForm"
            class="text-romm-green bg-toplayer"
            @click="createUser"
          >
            {{ t("common.create") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
