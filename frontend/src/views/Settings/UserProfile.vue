<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import RetroAchievements from "@/components/Settings/UserProfile/RetroAchievements.vue";
import RSection from "@/components/common/RSection.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeConfig from "@/stores/config";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath, getRoleIcon } from "@/utils";

const { t } = useI18n();
const auth = storeAuth();
const { user } = storeToRefs(auth);
const config = storeConfig();
const { config: configData } = storeToRefs(config);
const userToEdit = ref<UserItem | null>(null);
const usersStore = storeUsers();
const imagePreviewUrl = ref<string | undefined>("");
const emitter = inject<Emitter<Events>>("emitter");

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
  if (!userToEdit.value) return;

  userApi
    .updateUser(userToEdit.value)
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

  emitter?.emit("refreshDrawer", null);
}

onMounted(() => {
  userToEdit.value = { ...user.value, password: "", avatar: undefined };
  if (userToEdit.value) {
    document.title = `${userToEdit.value.username} | Profile`;
  }
});

onUnmounted(() => {
  imagePreviewUrl.value = "";
});
</script>
<template>
  <template v-if="userToEdit">
    <v-row class="ma-4" no-gutters>
      <v-col>
        <v-list-item>
          <template #prepend>
            <v-hover v-slot="{ isHovering, props }">
              <v-avatar size="100" v-bind="props">
                <v-img
                  :src="
                    imagePreviewUrl ||
                    (userToEdit.avatar_path
                      ? `/assets/romm/assets/${userToEdit.avatar_path}?ts=${userToEdit.updated_at}`
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
                    v-model="userToEdit.avatar"
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
          </template>
          <template #title>
            <v-list-item-title class="text-h6">
              {{ userToEdit.username }}
            </v-list-item-title>
          </template>
          <template #subtitle>
            <v-list-item-subtitle class="mt-2">
              {{ userToEdit.role
              }}<v-icon class="ml-1">
                {{ getRoleIcon(userToEdit.role) }}
              </v-icon>
            </v-list-item-subtitle>
          </template>
        </v-list-item>
      </v-col>
    </v-row>

    <RSection class="ma-4" icon="mdi-account" title="Account details">
      <template #content>
        <v-text-field
          v-model="userToEdit.username"
          class="ma-4"
          variant="outlined"
          :label="t('settings.username')"
          :rules="usersStore.usernameRules"
          required
          clearable
        />
        <v-text-field
          v-model="userToEdit.password"
          class="ma-4"
          variant="outlined"
          :label="t('settings.password')"
          :hint="t('settings.password-hint')"
          clearable
        />
        <v-text-field
          v-if="configData.EJS_NETPLAY_ENABLED"
          v-model="userToEdit.netplayid"
          class="ma-4"
          variant="outlined"
          :label="t('settings.netplay-id')"
          :rules="usersStore.netplayIdRules"
          :hint="t('settings.netplay-id-hint')"
          clearable
        />
        <v-text-field
          v-model="userToEdit.email"
          class="ma-4"
          variant="outlined"
          :label="t('settings.email')"
          :rules="usersStore.emailRules"
          required
          clearable
        />
        <v-select
          v-model="userToEdit.role"
          class="ma-4"
          variant="outlined"
          :items="['viewer', 'editor', 'admin']"
          :label="t('settings.role')"
          required
          hide-details
        >
          <template #selection="{ item }">
            <v-list-item class="pa-0">
              <v-icon class="mr-2">
                {{ getRoleIcon(item.title) }}
              </v-icon>
              {{ item.title }}
            </v-list-item>
          </template>
          <template #item="{ item }">
            <v-list-item :title="item.title">
              <template #prepend>
                <v-icon>{{ getRoleIcon(item.title) }}</v-icon>
              </template>
            </v-list-item>
          </template>
        </v-select>
        <v-btn
          :variant="!userToEdit.username ? 'plain' : 'flat'"
          :disabled="!userToEdit.username"
          class="ml-4 text-romm-green bg-toplayer"
          @click="editUser"
        >
          {{ t("common.apply") }}
        </v-btn>
      </template>
    </RSection>

    <RetroAchievements class="mx-4 mt-8" />
  </template>
</template>
