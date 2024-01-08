<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { UserItem, Events } from "@/types/emitter";
import api from "@/services/api";
import storeUsers from "@/stores/users";

const user = ref<UserItem | null>(null);
const show = ref(false);
const usersStore = storeUsers();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteUserDialog", (userToDelete) => {
  user.value = userToDelete;
  show.value = true;
});

async function deleteUser() {
  if (!user.value) return;

  await api.deleteUser(user.value)
    .then(() => {
      if (user.value) usersStore.remove(user.value.id);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to delete user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
      });
    });

  show.value = false;
}
</script>
<template>
  <v-dialog v-if="user" v-model="show" max-width="500px" :scrim="true">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
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
        <v-row class="justify-center pa-2" no-gutters>
          <span class="mr-1">Deleting</span
          ><span class="text-romm-accent-1">{{ user.username }}</span
          >.<span class="ml-1">Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn class="bg-terciary text-romm-red ml-5" @click="deleteUser()"
            >Confirm</v-btn
          >
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
