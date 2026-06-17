<script setup lang="ts">
// UserProfile — v2-native rewrite. Layout:
//   • page title
//   • flush identity row (96px bordered avatar + username + role chip
//     + secondary metadata: joined + last active)
//   • Account Details section (form rows + Discard / Apply buttons,
//     password handled by ChangePasswordDialog)
//   • RetroAchievements section (own component)
//
// While `userToEdit` is loading we render a thin skeleton so the
// layout doesn't pop in. Apply is disabled until the form is dirty;
// Discard restores the original snapshot.
import {
  RBtn,
  RIcon,
  RSelect,
  RSkeletonBlock,
  RTag,
  RTextField,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { formatTimestamp, getRoleIcon } from "@/utils";
import ChangePasswordDialog from "@/v2/components/Settings/ChangePasswordDialog.vue";
import RetroAchievementsSection from "@/v2/components/Settings/RetroAchievementsSection.vue";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

const { t, locale } = useI18n();
const auth = storeAuth();
const { user } = storeToRefs(auth);
const userToEdit = ref<UserItem | null>(null);
const originalSnapshot = ref<Pick<
  UserItem,
  "username" | "email" | "role"
> | null>(null);
const usersStore = storeUsers();
const imagePreviewUrl = ref<string | undefined>("");
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const fileInputRef = ref<HTMLInputElement | null>(null);
const submitting = ref(false);
const passwordDialogOpen = ref(false);

const roleItems = computed(() =>
  ["viewer", "editor", "admin"].map((role) => ({
    title: t(`settings.role-${role}`),
    value: role,
  })),
);

type RoleTone = "brand" | "warning" | "info";
const ROLE_TONE: Record<string, RoleTone> = {
  admin: "brand",
  editor: "warning",
  viewer: "info",
};
function roleToneFor(role: string | undefined): RoleTone {
  if (role && role in ROLE_TONE) return ROLE_TONE[role];
  return "info";
}

// Header reflects the SAVED user (auth store), not the in-progress
// edits — typing in the form fields shouldn't redraw the identity row
// in real time; it only refreshes after Apply succeeds and
// `auth.setCurrentUser(data)` rehydrates `user`.
const avatarSrc = computed(() => {
  if (imagePreviewUrl.value) return imagePreviewUrl.value;
  return userAvatarUrl(user.value?.avatar_path, user.value?.updated_at);
});

const isDirty = computed(() => {
  if (!userToEdit.value || !originalSnapshot.value) return false;
  return (
    userToEdit.value.username !== originalSnapshot.value.username ||
    (userToEdit.value.email ?? "") !== (originalSnapshot.value.email ?? "") ||
    userToEdit.value.role !== originalSnapshot.value.role ||
    !!userToEdit.value.avatar
  );
});

function snapshot(item: UserItem) {
  originalSnapshot.value = {
    username: item.username,
    email: item.email,
    role: item.role,
  };
}

function reset() {
  if (!user.value) return;
  userToEdit.value = { ...user.value, password: "", avatar: undefined };
  imagePreviewUrl.value = "";
  if (userToEdit.value) snapshot(userToEdit.value);
}

function triggerFileInput() {
  fileInputRef.value?.click();
}

function previewImage(event: Event) {
  const input = event.target as HTMLInputElement;
  if (!input.files || !input.files[0] || !userToEdit.value) return;
  const file = input.files[0];
  userToEdit.value.avatar = file;
  const reader = new FileReader();
  reader.onload = () => {
    imagePreviewUrl.value = reader.result?.toString();
  };
  reader.readAsDataURL(file);
}

async function applyChanges() {
  if (!userToEdit.value || !isDirty.value) return;
  submitting.value = true;
  try {
    const { data } = await userApi.updateUser(userToEdit.value);
    snackbar.success(
      t("settings.user-updated-successfully", { username: data.username }),
      { icon: "mdi-check-bold" },
    );
    usersStore.update(data);
    if (data.id === auth.user?.id) auth.setCurrentUser(data);
    emitter?.emit("refreshDrawer", null);
    if (userToEdit.value) snapshot(userToEdit.value);
    userToEdit.value.avatar = undefined;
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.unable-to-edit-user", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}

const joinedLabel = computed(() =>
  user.value?.created_at
    ? t("settings.profile-joined", {
        date: formatTimestamp(user.value.created_at, locale.value),
      })
    : null,
);

const lastActiveLabel = computed(() =>
  user.value?.last_active
    ? t("settings.profile-last-active", {
        date: formatTimestamp(user.value.last_active, locale.value),
      })
    : null,
);

onMounted(() => {
  reset();
  if (userToEdit.value) {
    document.title = `${userToEdit.value.username} | ${t("common.profile")}`;
  }
});

onUnmounted(() => {
  imagePreviewUrl.value = "";
});
</script>

<template>
  <div class="r-v2-section-stack">
    <template v-if="userToEdit">
      <!-- Identity row — flush (no card chrome). -->
      <div class="r-v2-profile__identity-row">
        <button
          type="button"
          class="r-v2-profile__avatar"
          :aria-label="t('settings.change-avatar')"
          @click="triggerFileInput"
        >
          <img :src="avatarSrc" :alt="user?.username ?? ''" />
          <span class="r-v2-profile__avatar-edit">
            <RIcon icon="mdi-pencil" size="20" />
          </span>
        </button>
        <input
          ref="fileInputRef"
          type="file"
          accept="image/*"
          class="r-v2-profile__file"
          :aria-label="t('settings.change-avatar')"
          @change="previewImage"
        />
        <div class="r-v2-profile__identity">
          <div class="r-v2-profile__name-row">
            <span class="r-v2-profile__username">
              {{ user?.username }}
            </span>
            <RTag
              v-if="user?.role"
              :icon="getRoleIcon(user.role)"
              :tone="roleToneFor(user.role)"
              size="small"
              class="r-v2-profile__role-tag"
            >
              {{ user.role }}
            </RTag>
          </div>
          <div class="r-v2-profile__meta">
            <div v-if="user?.email" class="r-v2-profile__meta-row">
              <RTag tone="plain" prepend-icon="mdi-email-outline">
                {{ user.email }}
              </RTag>
            </div>
            <div
              v-if="joinedLabel || lastActiveLabel"
              class="r-v2-profile__meta-row"
            >
              <RTag
                v-if="joinedLabel"
                tone="plain"
                prepend-icon="mdi-calendar-blank-outline"
              >
                {{ joinedLabel }}
              </RTag>
              <RTag
                v-if="lastActiveLabel"
                tone="plain"
                prepend-icon="mdi-clock-outline"
              >
                {{ lastActiveLabel }}
              </RTag>
            </div>
          </div>
        </div>
      </div>

      <!-- Account details -->
      <SettingsSection
        :title="t('settings.account-details')"
        icon="mdi-account"
      >
        <div class="r-v2-profile__field">
          <RTextField
            v-model="userToEdit.username"
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
        </div>
        <div class="r-v2-profile__field">
          <RTextField
            v-model="userToEdit.email"
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
        </div>
        <div class="r-v2-profile__field">
          <RSelect
            v-model="userToEdit.role"
            :items="roleItems"
            prefix-label="stacked"
            required
            hide-details
          >
            <template #prefix-label>
              <RIcon icon="mdi-shield-account-outline" size="14" />
              {{ t("settings.role") }}
            </template>
            <template #selection="{ item }">
              <div class="r-v2-profile__role-line">
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

        <!-- Password — visually identical to the other prefix-label
             rows, but the value is a fixed mask and the change flow is
             driven by the dialog (opened from the append-inner button).
             readonly + type=password keeps the field non-editable while
             still reading semantically as a password field. -->
        <div class="r-v2-profile__field">
          <RTextField
            model-value="00000000"
            type="password"
            prefix-label="stacked"
            readonly
            hide-details
            autocomplete="new-password"
          >
            <template #prefix-label>
              <RIcon icon="mdi-key-outline" size="14" />
              {{ t("settings.password") }}
            </template>
            <template #append-inner>
              <RBtn
                variant="text"
                size="small"
                prepend-icon="mdi-key-variant"
                class="r-v2-profile__pwd-btn"
                @click="passwordDialogOpen = true"
              >
                {{ t("settings.change-password") }}
              </RBtn>
            </template>
          </RTextField>
        </div>

        <div class="r-v2-profile__actions">
          <RBtn
            variant="flat"
            color="primary"
            :loading="submitting"
            :disabled="!isDirty || !userToEdit.username"
            prepend-icon="mdi-check"
            @click="applyChanges"
          >
            {{ t("common.apply") }}
          </RBtn>
        </div>
      </SettingsSection>

      <RetroAchievementsSection />
    </template>

    <!-- Skeleton — shown until userToEdit is hydrated from auth.user. -->
    <template v-else>
      <div class="r-v2-profile__identity-row">
        <RSkeletonBlock
          shape="circle"
          width="96px"
          height="96px"
          class="r-v2-profile__avatar-skeleton"
        />
        <div class="r-v2-profile__identity">
          <RSkeletonBlock width="160px" height="22px" />
          <div class="r-v2-profile__meta">
            <RSkeletonBlock width="220px" height="12px" />
            <RSkeletonBlock width="180px" height="12px" />
          </div>
        </div>
      </div>
      <RSkeletonBlock width="100%" height="280px" />
    </template>

    <ChangePasswordDialog
      v-model:open="passwordDialogOpen"
      :user-id="userToEdit?.id ?? null"
    />
  </div>
</template>

<style scoped>
/* Identity row — flush, taller (96px avatar). */
.r-v2-profile__identity-row {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 28px;
}

.r-v2-profile__avatar {
  position: relative;
  appearance: none;
  padding: 0;
  background: var(--r-color-surface);
  cursor: pointer;
  border-radius: 50%;
  overflow: hidden;
  width: 96px;
  height: 96px;
  flex-shrink: 0;
  border: 1px solid var(--r-color-border-strong);
  transition:
    border-color var(--r-motion-fast) var(--r-motion-ease-out),
    box-shadow var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-profile__avatar:hover {
  border-color: var(--r-color-brand-primary);
  box-shadow: 0 0 0 4px
    color-mix(in srgb, var(--r-color-brand-primary) 18%, transparent);
}
.r-v2-profile__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.r-v2-profile__avatar-edit {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, black 50%, transparent);
  color: var(--r-color-overlay-fg);
  opacity: 0;
  transition: opacity var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-profile__avatar:hover .r-v2-profile__avatar-edit,
.r-v2-profile__avatar:focus-visible .r-v2-profile__avatar-edit {
  opacity: 1;
}
.r-v2-profile__avatar-skeleton {
  flex-shrink: 0;
}

.r-v2-profile__file {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.r-v2-profile__identity {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.r-v2-profile__name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.r-v2-profile__username {
  font-size: 22px;
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
  line-height: 1.1;
  letter-spacing: -0.01em;
}

/* Role tag — RTag handles the base look + tone-based tint. `capitalize`
   only uppercases the first letter (e.g. "admin" → "Admin"); the prior
   `uppercase` rendering read as a shout next to the username. */
.r-v2-profile__role-tag {
  text-transform: capitalize;
  letter-spacing: 0.02em;
}

/* Secondary metadata under the username. Email sits on its own row;
   joined + last active share the row below so the eye reads identity
   first, history second. Each item is an `<RTag tone="plain">` — the
   tag inherits the row's font-size and muted colour, so the metadata
   blends into a single sentence-style block. */
.r-v2-profile__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-profile__meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

/* Field rows — hairline-divided, padding mirrors the mock. */
.r-v2-profile__field {
  padding: 14px 16px;
  border-bottom: 1px solid var(--r-color-border);
}
.r-v2-profile__field:last-of-type {
  border-bottom: none;
}

/* Change-password button lives inside the password field's append-inner
   area — keep it compact so it doesn't blow out the row height. */
.r-v2-profile__pwd-btn {
  margin-right: 4px;
}

.r-v2-profile__actions {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  padding: 14px 16px;
  border-top: 1px solid var(--r-color-border);
}

.r-v2-profile__role-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
}
</style>
