<script setup lang="ts">
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/Dialog.vue";

// Props
const user = ref({
  username: "",
  password: "",
  role: "viewer",
});
const { mdAndDown, lgAndUp } = useDisplay();
const show = ref(false);
const usersStore = storeUsers();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateUserDialog", () => {
  show.value = true;
});

// Functions
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
}
</script>
<template>
  <r-dialog
    @close="closeDialog"
    v-model="show"
    icon="mdi-account"
    :width="lgAndUp ? '900px' : mdAndDown ? '570px' : '85vw'"
  >
    <template #content>
      <v-row no-gutters class="px-4">
        <v-col>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="user.username"
                rounded="0"
                variant="outlined"
                label="username"
                required
                hide-details
                clearable
              />
            </v-col>
          </v-row>
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="user.password"
                rounded="0"
                variant="outlined"
                label="Password"
                required
                hide-details
                clearable
              />
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
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center pa-2" no-gutters>
        <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
        <v-btn
          :disabled="!user.username || !user.password"
          class="text-romm-green bg-terciary ml-5"
          @click="createUser()"
        >
          Create
        </v-btn>
      </v-row>
    </template>
  </r-dialog>
</template>
