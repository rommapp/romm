<script setup lang="ts">
import type { Emitter } from "mitt";
import { inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath, getRoleIcon } from "@/utils";

const { t } = useI18n();
const user = ref<UserItem | null>(null);
const { lgAndUp } = useDisplay();
const show = ref(false);
const auth = storeAuth();
const validForm = ref(false);
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
        auth.setCurrentUser(data);
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
  <RDialog
    v-if="user"
    v-model="show"
    icon="mdi-pencil-box"
    :width="lgAndUp ? '45vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-row class="pl-2" no-gutters>
        {{ t("settings.edit-user") }}
      </v-row>
    </template>
    <template #content>
      <v-form v-model="validForm">
        <v-row class="align-center pa-2" no-gutters>
          <v-col cols="12" sm="8">
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
              :placeholder="t('settings.password-placeholder')"
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
              required
              clearable
              class="ma-2"
            />
            <v-select
              v-model="user.role"
              variant="outlined"
              :items="['viewer', 'editor', 'admin']"
              :label="t('settings.role')"
              required
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
                      <v-btn
                        v-if="isHovering"
                        class="d-flex translucent cursor-pointer h-100 w-100 align-center justify-center text-h4"
                        @click="triggerFileInput"
                      >
                        <v-icon>mdi-pencil</v-icon>
                      </v-btn>
                    </v-fade-transition>
                    <v-file-input
                      id="file-input"
                      v-model="user.avatar"
                      class="file-input text-truncate"
                      label="Avatar"
                      prepend-inner-icon="mdi-image"
                      prepend-icon=""
                      variant="outlined"
                      @change="previewImage"
                    />
                  </v-img>
                </v-avatar>
              </v-hover>
            </v-row>
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
            @click="editUser"
          >
            {{ t("common.apply") }}
          </v-btn>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
