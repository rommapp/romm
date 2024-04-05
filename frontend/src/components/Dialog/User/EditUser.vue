<script setup lang="ts">
import { ref, inject } from "vue";
import type { Emitter } from "mitt";
import type { Events, UserItem } from "@/types/emitter";

import userApi from "@/services/api/user";
import { defaultAvatarPath } from "@/utils";
import storeUsers from "@/stores/users";

const user = ref<UserItem | null>(null);
const show = ref(false);
const usersStore = storeUsers();

const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditUserDialog", (userToEdit) => {
  user.value = { ...userToEdit, avatar: undefined };
  show.value = true;
});

// Functions
function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function editUser() {
  if (!user.value) return;

  userApi
    .updateUser(user.value)
    .then(({ data }) => {
      emitter?.emit("snackbarShow", {
        msg: `User ${data.username} updated successfully`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 5000,
      });
      usersStore.update(data);
    })
    .catch(({ response, message }) => {
      emitter?.emit("snackbarShow", {
        msg: `Unable to edit user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000,
      });
    });

  show.value = false;
  emitter?.emit("refreshDrawer", null);
}

function closeDialog() {
  show.value = false;
}
</script>
<template>
  <v-dialog v-if="user" v-model="show" max-width="700px" :scrim="false">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-pencil-box" class="ml-5 mr-2" />
          </v-col>
          <v-col>
            <v-btn
              @click="closeDialog"
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
        <v-row class="align-center" no-gutters>
          <v-col cols="12" sm="8">
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
                ></v-select>
              </v-col>
            </v-row>
          </v-col>
          <v-col cols="12" sm="4">
            <v-row class="pa-2 justify-center" no-gutters>
              <v-hover v-slot="{ isHovering, props }">
                <v-avatar size="190" class="ml-4" v-bind="props">
                  <v-img
                    :src="
                      user.avatar_path
                        ? `/assets/romm/assets/${user.avatar_path}`
                        : defaultAvatarPath
                    "
                  >
                    <v-fade-transition>
                      <div
                        v-if="isHovering"
                        class="d-flex translucent v-card--reveal text-h4"
                        @click="triggerFileInput"
                      >
                        <v-icon>mdi-pencil</v-icon>
                      </div>
                    </v-fade-transition>
                    <v-file-input
                      id="file-input"
                      class="file-input text-truncate"
                      v-model="user.avatar"
                      label="Avatar"
                      prepend-inner-icon="mdi-image"
                      prepend-icon=""
                      variant="outlined"
                      hide-details
                    />
                  </v-img>
                </v-avatar>
              </v-hover>
            </v-row>
          </v-col>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="closeDialog" class="bg-terciary">Cancel</v-btn>
          <v-btn class="text-romm-green bg-terciary ml-5" @click="editUser()"
            >Apply</v-btn
          >
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.file-input {
  display: none;
}
.translucent {
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(2px);
}
.v-card--reveal {
  align-items: center;
  bottom: 0;
  justify-content: center;
  position: absolute;
  width: 100%;
  height: 100%;
  cursor: pointer;
}
</style>
