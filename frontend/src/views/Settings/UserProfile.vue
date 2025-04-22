<script setup lang="ts">
import RetroAchievements from "@/components/Settings/UserProfile/RetroAchievements.vue";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath, getRoleIcon } from "@/utils";
import { inject, ref, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";

// Props
const { t } = useI18n();
const auth = storeAuth();
const { user } = storeToRefs(auth);
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

  emitter?.emit("refreshDrawer", null);
}

onMounted(() => {
  userToEdit.value = { ...user.value, password: "", avatar: undefined };
});

onUnmounted(() => {
  imagePreviewUrl.value = "";
});
</script>
<template>
  <template v-if="userToEdit">
    <v-row no-gutters class="flex-column align-center mt-4">
      <v-hover v-slot="{ isHovering, props }">
        <v-avatar size="150" v-bind="props">
          <v-img
            :src="
              imagePreviewUrl ||
              (userToEdit.avatar_path
                ? `/assets/romm/assets/${userToEdit.avatar_path}?ts=${userToEdit.updated_at}`
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
    </v-row>
    <v-row no-gutters class="mt-4">
      <v-col cols="8" md="6" class="mx-auto">
        <v-text-field
          v-model="userToEdit.username"
          variant="outlined"
          :label="t('settings.username')"
          required
          hide-details
          clearable
        />
      </v-col>
    </v-row>
    <v-row no-gutters class="mt-4">
      <v-col cols="8" md="6" class="mx-auto">
        <v-text-field
          v-model="userToEdit.password"
          variant="outlined"
          :label="t('settings.password')"
          required
          hide-details
          clearable
        />
      </v-col>
    </v-row>
    <v-row no-gutters class="mt-4">
      <v-col cols="8" md="6" class="mx-auto">
        <v-text-field
          v-model="userToEdit.email"
          variant="outlined"
          label="email"
          required
          hide-details
          clearable
        />
      </v-col>
    </v-row>
    <v-row no-gutters class="mt-4">
      <v-col cols="8" md="6" class="mx-auto">
        <v-select
          v-model="userToEdit.role"
          variant="outlined"
          :items="['viewer', 'editor', 'admin']"
          :label="t('settings.role')"
          required
          hide-details
        >
          <template #selection="{ item }">
            <v-list-item class="pa-0">
              <v-icon class="mr-2">{{ getRoleIcon(item.title) }}</v-icon>
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
      </v-col>
    </v-row>
    <v-row no-gutters class="mt-4 text-center">
      <v-col cols="8" md="6" class="mx-auto">
        <v-btn
          :variant="!userToEdit.username ? 'plain' : 'flat'"
          :disabled="!userToEdit.username"
          class="text-romm-green bg-toplayer"
          @click="editUser"
        >
          {{ t("common.apply") }}
        </v-btn>
      </v-col>
    </v-row>
    <retro-achievements class="ma-4" />
  </template>
</template>
