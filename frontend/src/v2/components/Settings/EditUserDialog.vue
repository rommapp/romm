<script setup lang="ts">
// EditUserDialog — v2-native rebuild of v1
// `Settings/Administration/Users/Dialog/EditUser.vue`. Form + avatar
// upload. Listens for `showEditUserDialog` so the v2 UsersSection can
// open it via the existing emitter contract.
import { RBtn, RIcon, RSelect, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { defaultAvatarPath, getRoleIcon } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const auth = storeAuth();
const usersStore = storeUsers();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const show = ref(false);
const submitting = ref(false);
const user = ref<UserItem | null>(null);
const imagePreviewUrl = ref<string | undefined>(undefined);
const fileInputRef = ref<HTMLInputElement | null>(null);

emitter?.on("showEditUserDialog", (toEdit) => {
  user.value = { ...toEdit, password: "", avatar: undefined };
  imagePreviewUrl.value = undefined;
  show.value = true;
});

const avatarSrc = computed(() => {
  if (imagePreviewUrl.value) return imagePreviewUrl.value;
  if (user.value?.avatar_path) {
    return `/assets/romm/assets/${user.value.avatar_path}?ts=${user.value.updated_at}`;
  }
  return defaultAvatarPath;
});

const roleItems = computed(() =>
  ["viewer", "editor", "admin"].map((role) => ({
    title: role.charAt(0).toUpperCase() + role.slice(1),
    value: role,
  })),
);

function triggerFileInput() {
  fileInputRef.value?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files || !input.files[0] || !user.value) return;
  const file = input.files[0];
  user.value.avatar = file;
  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  reader.readAsDataURL(file);
}

async function editUser() {
  if (!user.value) return;
  submitting.value = true;
  try {
    const { data } = await userApi.updateUser(user.value);
    snackbar.success(`User ${data.username} updated`, {
      icon: "mdi-check-bold",
    });
    usersStore.update(data);
    if (data.id === auth.user?.id) auth.setCurrentUser(data);
    emitter?.emit("refreshDrawer", null);
    show.value = false;
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `Unable to edit user: ${
        e?.response?.data?.detail || e?.response?.statusText || e?.message
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}

function close() {
  show.value = false;
  imagePreviewUrl.value = undefined;
}
</script>

<template>
  <RDialog
    v-if="user"
    v-model="show"
    icon="mdi-account-edit"
    :width="640"
    @close="close"
  >
    <template #header>
      <span class="r-v2-user-dialog__title">{{ t("settings.edit-user") }}</span>
    </template>
    <template #content>
      <div class="r-v2-user-dialog__edit-grid">
        <div class="r-v2-user-dialog__form">
          <RTextField
            v-model="user.username"
            prefix-label="stacked"
            :rules="usersStore.usernameRules"
            required
            clearable
          >
            <template #prefix-label>
              <RIcon icon="mdi-account-outline" size="14" />
              {{ t("settings.username") }}
            </template>
          </RTextField>
          <RTextField
            v-model="user.password"
            prefix-label="stacked"
            :placeholder="t('settings.password-placeholder')"
            type="password"
            clearable
          >
            <template #prefix-label>
              <RIcon icon="mdi-key-outline" size="14" />
              {{ t("settings.password") }}
            </template>
          </RTextField>
          <RTextField
            v-model="user.email"
            prefix-label="stacked"
            :rules="usersStore.emailRules"
            type="email"
            required
            clearable
          >
            <template #prefix-label>
              <RIcon icon="mdi-email-outline" size="14" />
              {{ t("settings.email") }}
            </template>
          </RTextField>
          <RSelect
            v-model="user.role"
            variant="outlined"
            :items="roleItems"
            :label="t('settings.role')"
            required
            hide-details
          >
            <template #selection="{ item }">
              <div class="r-v2-user-dialog__role-line">
                <RIcon :icon="getRoleIcon(item.value)" size="16" />
                {{ item.title }}
              </div>
            </template>
            <template #item="{ props: itemProps, item }">
              <li v-bind="itemProps">
                <RIcon :icon="getRoleIcon(item.value)" size="16" />
                <span class="r-select__item-title">{{ item.title }}</span>
              </li>
            </template>
          </RSelect>
        </div>
        <button
          type="button"
          class="r-v2-user-dialog__avatar"
          :aria-label="t('settings.change-avatar', 'Change avatar')"
          @click="triggerFileInput"
        >
          <img :src="avatarSrc" :alt="user.username" />
          <span class="r-v2-user-dialog__avatar-edit">
            <RIcon icon="mdi-pencil" size="20" />
          </span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          class="r-v2-user-dialog__file"
          :aria-label="t('settings.change-avatar', 'Change avatar')"
          @change="previewImage"
        />
      </div>
    </template>
    <template #footer>
      <div class="r-v2-user-dialog__footer">
        <RBtn variant="text" @click="close">
          {{ t("common.cancel") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          :loading="submitting"
          :disabled="!user.username"
          @click="editUser"
        >
          {{ t("common.apply") }}
        </RBtn>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-user-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-user-dialog__edit-grid {
  display: grid;
  grid-template-columns: 1fr 160px;
  gap: 24px;
  padding: 20px 24px;
  align-items: start;
}
html[data-bp~="xs"] .r-v2-user-dialog__edit-grid {
  grid-template-columns: 1fr;
}
.r-v2-user-dialog__form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.r-v2-user-dialog__avatar {
  position: relative;
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  cursor: pointer;
  border-radius: 50%;
  overflow: hidden;
  width: 140px;
  height: 140px;
  flex-shrink: 0;
  justify-self: center;
}
.r-v2-user-dialog__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.r-v2-user-dialog__avatar-edit {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 50%, transparent);
  color: var(--r-color-overlay-fg);
  opacity: 0;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-user-dialog__avatar:hover .r-v2-user-dialog__avatar-edit,
.r-v2-user-dialog__avatar:focus-visible .r-v2-user-dialog__avatar-edit {
  opacity: 1;
}
.r-v2-user-dialog__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}
.r-v2-user-dialog__role-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}
.r-v2-user-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--r-color-border);
}
</style>
