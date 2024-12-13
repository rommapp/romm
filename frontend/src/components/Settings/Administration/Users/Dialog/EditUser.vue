<script setup lang="ts">
import RDialog from "@/components/common/RDialog.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath } from "@/utils";
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const user = ref<UserItem | null>(null);
const { lgAndUp } = useDisplay();
const show = ref(false);
const auth = storeAuth();
const usersStore = storeUsers();
const imagePreviewUrl = ref<string | undefined>("");
const emitter = inject<Emitter<Events>>("emitter");
emitter?.on("showEditUserDialog", (userToEdit) => {
  user.value = { ...userToEdit, password: "", avatar: undefined };
  show.value = true;
});

function triggerFileInput() {
  const fileInput = document.getElementById("file-input");
  fileInput?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files) return;

  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  if (input.files[0]) {
    reader.readAsDataURL(input.files[0]);
  }
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
      if (data.id == auth.user?.id) {
        auth.setUser(data);
      }
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
  imagePreviewUrl.value = "";
}
</script>
<template>
  <r-dialog
    v-if="user"
    @close="closeDialog"
    v-model="show"
    icon="mdi-pencil-box"
    :width="lgAndUp ? '45vw' : '95vw'"
  >
    <template #content>
      <v-row class="align-center pa-2" no-gutters>
        <v-col cols="12" sm="8">
          <v-row class="pa-2" no-gutters>
            <v-col>
              <v-text-field
                v-model="user.username"
                rounded="0"
                variant="outlined"
                :label="t('settings.username')"
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
                :label="t('settings.password')"
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
                :label="t('settings.role')"
                required
                hide-details
              />
            </v-col>
          </v-row>
        </v-col>
        <v-col cols="12" sm="4">
          <v-row class="pa-2 justify-center" no-gutters>
            <v-hover v-slot="{ isHovering, props }">
              <v-avatar size="190" class="ml-4" v-bind="props">
                <v-img
                  :src="
                    imagePreviewUrl ||
                    (user.avatar_path
                      ? `/assets/romm/assets/${user.avatar_path}?ts=${user.updated_at}`
                      : defaultAvatarPath)
                  "
                >
                  <v-fade-transition>
                    <div
                      v-if="isHovering"
                      class="d-flex translucent cursor-pointer h-100 align-center justify-center text-h4"
                      @click="triggerFileInput"
                    >
                      <v-icon>mdi-pencil</v-icon>
                    </div>
                  </v-fade-transition>
                  <v-file-input
                    id="file-input"
                    v-model="user.avatar"
                    class="file-input text-truncate"
                    label="Avatar"
                    prepend-inner-icon="mdi-image"
                    prepend-icon=""
                    variant="outlined"
                    hide-details
                    @change="previewImage"
                  />
                </v-img>
              </v-avatar>
            </v-hover>
          </v-row>
        </v-col>
      </v-row>
    </template>
    <template #append>
      <v-row class="justify-center mb-2" no-gutters>
        <v-btn-group divided density="compact">
          <v-btn class="bg-terciary" @click="closeDialog">
            {{ t("common.cancel") }}
          </v-btn>
          <v-btn
            :variant="!user.username ? 'plain' : 'flat'"
            :disabled="!user.username"
            class="text-romm-green bg-terciary"
            @click="editUser"
          >
            {{ t("common.apply") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </r-dialog>
</template>
