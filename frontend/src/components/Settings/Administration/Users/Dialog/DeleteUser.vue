<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import userApi from "@/services/api/user";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const user = ref<UserItem | null>(null);
const show = ref(false);
const usersStore = storeUsers();
const { lgAndUp } = useDisplay();
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
      emitter?.emit("snackbarShow", {
        msg: `User ${user.value.username} successfully removed!`,
        icon: "mdi-check",
        color: "romm-green",
        timeout: 4000,
      });
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to delete user ${user.value.username}: ${
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
    v-if="user"
    @close="closeDialog"
    v-model="show"
    icon="mdi-delete"
    :width="lgAndUp ? '45vw' : '95vw'"
  >
    <template #content>
      <v-row class="justify-center align-center pa-2" no-gutters>
        <span>Deleting</span>
        <v-avatar size="40" class="ml-1">
          <v-img
            :src="
              user.avatar_path
                ? `/assets/romm/assets/${user.avatar_path}?ts=${user.updated_at}`
                : defaultAvatarPath
            "
          >
          </v-img> </v-avatar
        ><span class="text-romm-accent-1 ml-1">{{ user.username }}</span
        ><span class="ml-1">user. Do you confirm?</span>
      </v-row></template
    >
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog"> Cancel </v-btn>
          <v-btn class="bg-terciary text-romm-red" @click="deleteUser()">
            Confirm
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
