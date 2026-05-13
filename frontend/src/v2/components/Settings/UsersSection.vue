<script setup lang="ts">
// UsersSection — v2-native rebuild of v1
// `Settings/Administration/Users/UsersTable.vue`. Lives inside a
// SettingsSection (header has "Add" + "Invite link" buttons) and
// renders the users table with avatar, role badge, last-active,
// enabled toggle, and edit/delete actions.
//
// Create / edit / invite dialogs are emitter-driven and live in
// AdminUserDialogs.vue (mounted alongside this section). Delete uses
// useConfirm directly.
import { RBtn, RIcon, RTextField, RTooltip } from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { defaultAvatarPath, formatTimestamp, getRoleIcon } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import SettingsToggleRow from "@/v2/components/Settings/SettingsToggleRow.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();

const search = ref("");

const filteredUsers = computed(() => {
  const q = search.value.trim().toLowerCase();
  const list = allUsers.value;
  if (!q) return list;
  return list.filter(
    (u) =>
      u.username.toLowerCase().includes(q) ||
      (u.email ?? "").toLowerCase().includes(q),
  );
});

function avatarSrc(user: User) {
  return user.avatar_path
    ? `/assets/romm/assets/${user.avatar_path}?ts=${user.updated_at}`
    : defaultAvatarPath;
}

async function toggleEnabled(user: User, enabled: boolean) {
  if (user.id === auth.user?.id) return; // self-disable not allowed
  user.enabled = enabled;
  try {
    await userApi.updateUser(user);
  } catch (err) {
    user.enabled = !enabled; // revert on failure
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `Unable to ${enabled ? "enable" : "disable"} user: ${
        e?.response?.data?.detail || e?.response?.statusText || e?.message
      }`,
      { icon: "mdi-close-circle" },
    );
  }
}

async function deleteUser(user: User) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: `Delete user "${user.username}"? This cannot be undone.`,
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: user.username,
  });
  if (!ok) return;
  try {
    await userApi.deleteUser(user);
    usersStore.remove(user.id);
    snackbar.success(`User ${user.username} successfully removed`, {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `Unable to delete user ${user.username}: ${
        e?.response?.data?.detail || e?.response?.statusText || e?.message
      }`,
      { icon: "mdi-close-circle" },
    );
  }
}

onMounted(async () => {
  try {
    const { data } = await userApi.fetchUsers();
    usersStore.set(data);
  } catch (err) {
    console.error(err);
  }
});
</script>

<template>
  <SettingsSection title="Users" icon="mdi-account-group">
    <template #header-actions>
      <RBtn
        variant="text"
        size="small"
        prepend-icon="mdi-share-variant"
        @click="emitter?.emit('showCreateInviteLinkDialog')"
      >
        {{ t("settings.invite-link") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="primary"
        size="small"
        prepend-icon="mdi-plus"
        @click="emitter?.emit('showCreateUserDialog', null)"
      >
        {{ t("common.add") }}
      </RBtn>
    </template>
    <div class="r-v2-users__search">
      <RTextField
        v-model="search"
        prefix-label="inline"
        :placeholder="t('common.search')"
        hide-details
        density="compact"
        aria-label="Search users"
      >
        <template #prefix-label>
          <RIcon icon="mdi-magnify" size="15" />
        </template>
      </RTextField>
    </div>
    <table class="r-v2-table r-v2-users__table">
      <thead>
        <tr>
          <th>{{ t("common.name") }}</th>
          <th>{{ t("settings.email") }}</th>
          <th>{{ t("settings.role") }}</th>
          <th>Last active</th>
          <th>Enabled</th>
          <th class="r-v2-table__col-actions" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="user in filteredUsers" :key="user.id">
          <td>
            <div class="r-v2-users__name">
              <img
                :src="avatarSrc(user)"
                :alt="user.username"
                class="r-v2-users__avatar"
              />
              <span>{{ user.username }}</span>
            </div>
          </td>
          <td class="r-v2-users__meta">{{ user.email || "—" }}</td>
          <td>
            <span class="r-v2-users__role">
              <RIcon :icon="getRoleIcon(user.role)" size="14" />
              {{ user.role }}
            </span>
          </td>
          <td class="r-v2-users__meta">
            {{
              user.last_active ? formatTimestamp(user.last_active, locale) : "—"
            }}
          </td>
          <td>
            <SettingsToggleRow
              :model-value="user.enabled"
              :title="user.enabled ? 'Enabled' : 'Disabled'"
              :disabled="user.id === auth.user?.id"
              class="r-v2-users__enabled"
              @update:model-value="(v) => toggleEnabled(user, v)"
            />
          </td>
          <td class="r-v2-table__col-actions">
            <RTooltip>
              <template #activator="{ props: tipProps }">
                <button
                  v-bind="tipProps"
                  type="button"
                  class="r-v2-icon-btn"
                  :aria-label="t('settings.edit-user')"
                  @click="emitter?.emit('showEditUserDialog', user)"
                >
                  <RIcon icon="mdi-pencil" size="14" />
                </button>
              </template>
              <span>{{ t("settings.edit-user") }}</span>
            </RTooltip>
            <RTooltip>
              <template #activator="{ props: tipProps }">
                <button
                  v-bind="tipProps"
                  type="button"
                  class="r-v2-icon-btn r-v2-icon-btn--danger"
                  :aria-label="t('common.delete')"
                  :disabled="user.id === auth.user?.id"
                  @click="deleteUser(user)"
                >
                  <RIcon icon="mdi-trash-can-outline" size="14" />
                </button>
              </template>
              <span>{{ t("common.delete") }}</span>
            </RTooltip>
          </td>
        </tr>
        <tr v-if="filteredUsers.length === 0">
          <td colspan="6" class="r-v2-users__empty">No users to show.</td>
        </tr>
      </tbody>
    </table>
  </SettingsSection>
</template>

<style scoped>
.r-v2-users__search {
  padding: 12px 14px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-users__table {
  width: 100%;
  border-collapse: collapse;
}

/* Reuse the same table styling as ExcludedSection / etc. */
.r-v2-table th {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
}
.r-v2-table td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--r-color-border);
  font-size: 13px;
  color: var(--r-color-fg);
  vertical-align: middle;
}
.r-v2-table tr:last-child td {
  border-bottom: none;
}
.r-v2-table tr:hover td {
  background: var(--r-color-surface);
}
.r-v2-table__col-actions {
  width: 1%;
  text-align: right;
  white-space: nowrap;
}

.r-v2-users__name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-users__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
}
.r-v2-users__role {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: capitalize;
  color: var(--r-color-fg-secondary);
}
.r-v2-users__meta {
  color: var(--r-color-fg-muted);
}
.r-v2-users__enabled {
  padding: 0;
  background: transparent;
  width: auto;
}
.r-v2-users__enabled :deep(.r-v2-toggle-row__info) {
  display: none;
}
.r-v2-users__empty {
  text-align: center;
  color: var(--r-color-fg-muted);
  padding: 24px;
}

.r-v2-icon-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--r-color-fg-muted);
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-icon-btn:hover:not(:disabled) {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.r-v2-icon-btn--danger {
  color: color-mix(in srgb, var(--r-color-danger) 70%, transparent);
}
.r-v2-icon-btn--danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--r-color-danger) 12%, transparent);
  color: var(--r-color-danger);
}
</style>
