<script setup>
import { ref, inject } from "vue";

import { createUserApi } from "@/services/api";

const user = ref({
  username: "",
  password: "",
  role: "viewer",
});
const show = ref(false);

const emitter = inject("emitter");
emitter.on("showCreateUserDialog", () => {
  show.value = true;
});

async function createUser() {
  await createUserApi(user.value).catch(({ response, message }) => {
    emitter.emit("snackbarShow", {
      msg: `Unable to create user: ${
        response?.data?.detail || response?.statusText || message
      }`,
      icon: "mdi-close-circle",
      color: "red",
    });
  });
  show.value = false;
  emitter.emit("refreshView");
}
</script>
<template>
  <v-dialog v-model="show" max-width="500px" :scrim="false">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-account" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              @click="show = false"
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
            />
          </v-col>
        </v-row>
      </v-toolbar>
      <v-divider class="border-opacity-25" :thickness="1" />

      <v-card-text>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-text-field
              rounded="0"
              variant="outlined"
              v-model="user.username"
              label="username"
              required
              hide-details
              clearable
            ></v-text-field>
          </v-col>
        </v-row>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-text-field
              rounded="0"
              variant="outlined"
              v-model="user.password"
              label="Password"
              required
              hide-details
              clearable
            ></v-text-field>
          </v-col>
        </v-row>
        <v-row class="pa-2" no-gutters>
          <v-col>
            <v-select
              v-model="user.role"
              rounded="0"
              variant="outlined"
              :items="['viewer', 'editor', 'admin']"
              label="Role"
              required
              hide-details
            />
          </v-col>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn
            :disabled="!user.username || !user.password"
            class="text-romm-green bg-terciary ml-5"
            @click="createUser()"
          >
            Create
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
