<script setup lang="ts">
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events, UserItem } from "@/types/emitter";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";

const user = ref<UserItem | null>(null);
const show = ref(false);
const usersStore = storeUsers();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showDeleteUserDialog", (userToDelete) => {
  user.value = { password: "", ...userToDelete };
  show.value = true;
});

// Functions
async function deleteUser() {
  if (!user.value) return;

  await userApi
    .deleteUser(user.value)
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

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <v-dialog
    v-if="user"
    v-model="show"
    width="auto"
    no-click-animation
    persistent
    @click:outside="closeDialog"
    @keydown.esc="closeDialog"
  >
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-delete" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              class="bg-terciary"
              rounded="0"
              variant="text"
              icon="mdi-close"
              block
              @click="closeDialog"
            />
          </v-col>
        </v-row>
      </v-toolbar>

      <v-divider />

      <v-card-text>
        <v-row class="justify-center align-center pa-2" no-gutters>
          <span>Deleting</span>
          <v-avatar size="40" class="ml-1">
            <v-img
              :src="
                user.avatar_path
                  ? `/assets/romm/assets/${user.avatar_path}`
                  : defaultAvatarPath
              "
            >
            </v-img> </v-avatar
          ><span class="text-romm-accent-1 ml-1">{{ user.username }}</span
          ><span class="ml-1">user. Do you confirm?</span>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="bg-terciary text-romm-red ml-5" @click="deleteUser()">
            Confirm
          </v-btn>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
