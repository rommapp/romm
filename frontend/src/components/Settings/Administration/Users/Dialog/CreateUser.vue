<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const user = ref({
  username: "",
  password: "",
  email: "",
  role: "viewer",
});
const { lgAndUp } = useDisplay();
const show = ref(false);
const usersStore = storeUsers();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showCreateUserDialog", () => {
  show.value = true;
});

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
    :width="lgAndUp ? '60vw' : '95vw'"
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
              <v-text-field
                v-model="user.email"
                rounded="0"
                variant="outlined"
                label="email"
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
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn
            :disabled="!user.username || !user.password"
            :variant="!user.username || !user.password ? 'plain' : 'flat'"
            class="text-romm-green bg-terciary"
            @click="createUser()"
          >
            Create
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
