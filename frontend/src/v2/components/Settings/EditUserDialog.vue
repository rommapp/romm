<script setup lang="ts">
// EditUserDialog — edit a user's profile AND access in one place. Profile
// fields (username/password/email/avatar) plus an Access section that replaces
// the old role picker: an Admin toggle, and for non-admins the permission
// group and the platforms hidden from them. Emitter-driven
// (`showEditUserDialog`).
import { RBtn, RIcon, RSelect, RSwitch, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { OverrideSchemaIO, PermAction, PermEntity } from "@/__generated__";
import permissionsApi from "@/services/api/permissions";
import platformApi from "@/services/api/platform";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storePermissionGroups from "@/stores/permissionGroups";
import type { Platform } from "@/stores/platforms";
import storeUsers from "@/stores/users";
import type { Events } from "@/types/emitter";
import type { UserItem } from "@/types/user";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";
import { userAvatarUrl } from "@/v2/utils/userAvatar";
import HiddenGamesPicker from "./HiddenGamesPicker.vue";
import HiddenPlatformsPicker from "./HiddenPlatformsPicker.vue";
import OverridesMatrix from "./OverridesMatrix.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const auth = storeAuth();
const usersStore = storeUsers();
const groupsStore = storePermissionGroups();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

const show = ref(false);
const submitting = ref(false);
const user = ref<UserItem | null>(null);
const confirmPassword = ref("");
const imagePreviewUrl = ref<string | undefined>(undefined);
const fileInputRef = ref<HTMLInputElement | null>(null);

// Access section.
const isAdmin = ref(false);
const platforms = ref<Platform[]>([]);
const groupId = ref<number | null>(null);
const originalGroupId = ref<number | null>(null);
const hiddenPlatformIds = ref<number[]>([]);
const originalHiddenPlatformIds = ref<number[]>([]);

// Advanced: per-user overrides + per-game hiding.
const showAdvanced = ref(false);
const entities = ref<PermEntity[]>([]);
const actions = ref<PermAction[]>([]);
const overrides = ref<OverrideSchemaIO[]>([]);
const originalOverrides = ref<OverrideSchemaIO[]>([]);
const hiddenRomIds = ref<number[]>([]);
const originalHiddenRomIds = ref<number[]>([]);

function overridesKey(list: OverrideSchemaIO[]): string {
  return JSON.stringify(
    [...list].sort((a, b) =>
      `${a.entity}.${a.action}`.localeCompare(`${b.entity}.${b.action}`),
    ),
  );
}

async function ensureCatalog() {
  if (entities.value.length) return;
  try {
    const { data } = await permissionsApi.fetchCatalog();
    entities.value = data.entities;
    actions.value = data.actions;
  } catch (err) {
    console.error("Failed to load permission catalog", err);
  }
}

const editingSelf = computed(() => user.value?.id === auth.user?.id);

const groupItems = computed(() =>
  groupsStore.groups.map((g) => ({ title: g.name, value: g.id })),
);

const sortedPlatforms = computed(() =>
  [...platforms.value].sort((a, b) =>
    a.display_name.localeCompare(b.display_name),
  ),
);

emitter?.on("showEditUserDialog", async (toEdit) => {
  user.value = { ...toEdit, password: "", avatar: undefined };
  confirmPassword.value = "";
  imagePreviewUrl.value = undefined;
  isAdmin.value = toEdit.role === "admin";
  showAdvanced.value = false;
  show.value = true;

  try {
    const [perms, , platformsResp] = await Promise.all([
      permissionsApi.fetchUserPermissions(toEdit.id),
      groupsStore.ensureLoaded(),
      platforms.value.length
        ? Promise.resolve(null)
        : platformApi.getPlatforms(),
      ensureCatalog(),
    ]);
    if (platformsResp) platforms.value = platformsResp.data;
    // A null group means the user follows the server default group; show it
    // as selected so the picker never displays a meaningless empty option.
    const defaultGroupId = groupsStore.defaultGroup?.id ?? null;
    groupId.value = perms.data.permission_group_id ?? defaultGroupId;
    originalGroupId.value = groupId.value;

    const hiddenPlatforms = perms.data.hidden
      .filter((h) => h.entity === "platforms")
      .map((h) => h.entity_id);
    hiddenPlatformIds.value = [...hiddenPlatforms];
    originalHiddenPlatformIds.value = [...hiddenPlatforms];

    const hiddenRoms = perms.data.hidden
      .filter((h) => h.entity === "roms")
      .map((h) => h.entity_id);
    hiddenRomIds.value = [...hiddenRoms];
    originalHiddenRomIds.value = [...hiddenRoms];

    overrides.value = perms.data.overrides.map((o) => ({ ...o }));
    originalOverrides.value = perms.data.overrides.map((o) => ({ ...o }));
  } catch (err) {
    console.error("Failed to load user permissions", err);
  }
});

const avatarSrc = computed(() => {
  if (imagePreviewUrl.value) return imagePreviewUrl.value;
  return userAvatarUrl({
    userId: user.value?.id,
    avatarPath: user.value?.avatar_path,
    updatedAt: user.value?.updated_at,
  });
});

const confirmPasswordRules = computed(() => [
  (v: string) =>
    !user.value?.password || !!v || t("settings.repeat-password-required"),
  (v: string) =>
    v === (user.value?.password ?? "") || t("settings.passwords-must-match"),
]);

const passwordChangeValid = computed(() => {
  const pw = user.value?.password ?? "";
  if (!pw) return true;
  return pw.length >= 6 && pw === confirmPassword.value;
});

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

function diffHidden(
  entity: PermEntity,
  current: number[],
  original: number[],
  userId: number,
): Promise<unknown>[] {
  const added = current.filter((id) => !original.includes(id));
  const removed = original.filter((id) => !current.includes(id));
  return [
    ...added.map((id) =>
      permissionsApi.addHiddenEntity({
        entity,
        entity_id: id,
        user_id: userId,
      }),
    ),
    ...removed.map((id) =>
      permissionsApi.removeHiddenEntity({
        entity,
        entity_id: id,
        user_id: userId,
      }),
    ),
  ];
}

async function save() {
  if (!user.value) return;
  submitting.value = true;
  const userId = user.value.id;
  try {
    // Role is derived from the Admin toggle (admin vs plain user). Self-role
    // changes are ignored by the backend, so leave it untouched when editing
    // yourself.
    if (!editingSelf.value) {
      user.value.role = isAdmin.value ? "admin" : "user";
    }
    const { data } = await userApi.updateUser(user.value);

    // Group, overrides and hidden entities apply to non-admins (admins bypass).
    let nextGroupId = data.permission_group_id;
    if (!isAdmin.value) {
      const groupChanged = groupId.value !== originalGroupId.value;
      const overridesChanged =
        overridesKey(overrides.value) !== overridesKey(originalOverrides.value);
      if (groupChanged || overridesChanged) {
        await permissionsApi.updateUserPermissions(userId, {
          set_group: groupChanged,
          permission_group_id: groupId.value,
          overrides: overridesChanged ? overrides.value : undefined,
        });
        if (groupChanged) nextGroupId = groupId.value;
      }
      await Promise.all([
        ...diffHidden(
          "platforms",
          hiddenPlatformIds.value,
          originalHiddenPlatformIds.value,
          userId,
        ),
        ...diffHidden(
          "roms",
          hiddenRomIds.value,
          originalHiddenRomIds.value,
          userId,
        ),
      ]);
    }

    snackbar.success(t("settings.user-updated", { username: data.username }), {
      icon: "mdi-check-bold",
    });
    usersStore.update({ ...data, permission_group_id: nextGroupId });
    if (data.id === auth.user?.id) auth.setCurrentUser(data);
    emitter?.emit("refreshDrawer", null);
    show.value = false;
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
    scroll-content
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
            autocomplete="new-password"
            clearable
          >
            <template #prefix-label>
              <RIcon icon="mdi-key-outline" size="14" />
              {{ t("settings.password") }}
            </template>
          </RTextField>
          <RTextField
            v-if="user.password"
            v-model="confirmPassword"
            prefix-label="stacked"
            :rules="confirmPasswordRules"
            type="password"
            autocomplete="new-password"
            required
            clearable
          >
            <template #prefix-label>
              <RIcon icon="mdi-key-variant" size="14" />
              {{ t("settings.repeat-password") }}
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
        </div>
        <!-- Avatar is an image-upload control, not a text/icon button: it keeps
             a native <button> (matches v2's raw-<img> avatar convention). -->
        <button
          type="button"
          class="r-v2-user-dialog__avatar"
          :aria-label="t('settings.change-avatar')"
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
          :aria-label="t('settings.change-avatar')"
          @change="previewImage"
        />
      </div>

      <div class="r-v2-user-dialog__access">
        <span class="r-v2-user-dialog__access-label">
          <RIcon icon="mdi-shield-account-outline" size="14" />
          {{ t("settings.access") }}
        </span>

        <div class="r-v2-user-dialog__admin">
          <RSwitch
            v-model="isAdmin"
            :disabled="editingSelf"
            :label="t('settings.administrator')"
          />
          <span class="r-v2-user-dialog__hint">
            {{
              editingSelf
                ? t("settings.cannot-change-own-role")
                : t("settings.administrator-hint")
            }}
          </span>
        </div>

        <template v-if="!isAdmin">
          <div class="r-v2-user-dialog__field">
            <span class="r-v2-user-dialog__field-label">
              {{ t("settings.permission-group") }}
            </span>
            <RSelect
              v-model="groupId"
              variant="outlined"
              :items="groupItems"
              item-title="title"
              item-value="value"
              hide-details
            />
          </div>
          <div class="r-v2-user-dialog__field">
            <span class="r-v2-user-dialog__field-label">
              {{ t("settings.hidden-platforms") }}
            </span>
            <HiddenPlatformsPicker
              v-model="hiddenPlatformIds"
              :platforms="sortedPlatforms"
            />
          </div>

          <RBtn
            block
            variant="text"
            size="small"
            :prepend-icon="
              showAdvanced ? 'mdi-chevron-down' : 'mdi-chevron-right'
            "
            :aria-expanded="showAdvanced"
            class="r-v2-user-dialog__advanced-toggle"
            @click="showAdvanced = !showAdvanced"
          >
            {{ t("settings.advanced-permissions") }}
          </RBtn>

          <template v-if="showAdvanced">
            <div class="r-v2-user-dialog__field">
              <span class="r-v2-user-dialog__field-label">
                {{ t("settings.permission-overrides") }}
              </span>
              <span class="r-v2-user-dialog__hint">
                {{ t("settings.permission-overrides-hint") }}
              </span>
              <OverridesMatrix
                v-model="overrides"
                :entities="entities"
                :actions="actions"
              />
            </div>
            <div class="r-v2-user-dialog__field">
              <span class="r-v2-user-dialog__field-label">
                {{ t("settings.hidden-games") }}
              </span>
              <HiddenGamesPicker v-model="hiddenRomIds" />
            </div>
          </template>
        </template>
      </div>
    </template>
    <template #footer>
      <RBtn variant="text" @click="close">
        {{ t("common.cancel") }}
      </RBtn>
      <div style="flex: 1" />
      <RBtn
        variant="flat"
        color="primary"
        :loading="submitting"
        :disabled="!user.username || !passwordChangeValid"
        @click="save"
      >
        {{ t("common.apply") }}
      </RBtn>
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

.r-v2-user-dialog__access {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--r-color-border);
}
.r-v2-user-dialog__access-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-secondary);
}
.r-v2-user-dialog__admin {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.r-v2-user-dialog__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.r-v2-user-dialog__field-label {
  font-size: 12px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-secondary);
}
.r-v2-user-dialog__hint {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-user-dialog__advanced-toggle {
  align-self: flex-start;
}
</style>
