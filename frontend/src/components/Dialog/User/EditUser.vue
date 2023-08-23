<script setup>
import { ref, inject } from "vue";
import { updateUserApi } from "@/services/api";
import { defaultAvatarPath } from "@/utils/utils"

const user = ref();
const show = ref(false);
const avatarFile = ref();

const emitter = inject("emitter");
emitter.on("showEditUserDialog", (userToEdit) => {
  user.value = userToEdit;
  show.value = true;
});

function editUser() {
  updateUserApi(user.value)
    .then((response) => {
      emitter.emit("snackbarShow", {
        msg: `User ${response.data.username} updated successfully`,
        icon: "mdi-check-bold",
        color: "green",
        timeout: 5000
      });
    })
    .catch(({ response, message }) => {
      emitter.emit("snackbarShow", {
        msg: `Unable to edit user: ${
          response?.data?.detail || response?.statusText || message
        }`,
        icon: "mdi-close-circle",
        color: "red",
        timeout: 5000
      });
    });
  show.value = false;
  emitter.emit("refreshView");
  emitter.emit("refreshDrawer");
}
</script>
<template>
  <v-dialog v-model="show" max-width="700px" :scrim="false">
    <v-card>
      <v-toolbar density="compact" class="bg-terciary">
        <v-row class="align-center" no-gutters>
          <v-col cols="10">
            <v-icon icon="mdi-pencil-box" class="ml-5 mr-2" />
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
        <v-row no-gutters>
          <v-col cols="12" lg="9">
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
          <v-col cols="12" lg="3">
            <v-row class="pa-2 justify-center" no-gutters>
              <v-avatar size="128" class="">
                <v-img
                  :src="
                    user.avatar_path
                      ? `/assets/romm/resources/${user.avatar_path}`
                      : defaultAvatarPath
                  "
                />
              </v-avatar>
            </v-row>
            <v-row class="pa-2" no-gutters>
              <v-col>
                <v-file-input
                  class="text-truncate"
                  @keyup.enter="updateRom()"
                  v-model="user.avatar"
                  label="Avatar"
                  prepend-inner-icon="mdi-image"
                  prepend-icon=""
                  variant="outlined"
                  hide-details
                />
              </v-col>
            </v-row>
          </v-col>
        </v-row>
        <v-row class="justify-center pa-2" no-gutters>
          <v-btn @click="show = false" class="bg-terciary">Cancel</v-btn>
          <v-btn class="text-romm-green bg-terciary ml-5" @click="editUser()"
            >Apply</v-btn
          >
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
