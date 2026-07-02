<script setup lang="ts">
// UsersSection — v2-native users table.
//
// Layout mirrors LibraryManagement's tabs: a search bar at the top,
// the table itself (RTable), and the action buttons (Add + Invite)
// pinned at the bottom of the section. No SettingsSection wrapper —
// the tab in Administration owns the page chrome now.
//
// Create / edit / invite dialogs are emitter-driven; their components
// are mounted alongside in Administration.vue. Delete uses useConfirm
// directly (no dedicated dialog).
import {
  RBtn,
  RIcon,
  RSwitch,
  RTable,
  RTag,
  RTextField,
  RTooltip,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { PermissionGroupSchema } from "@/__generated__";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import storePermissionGroups from "@/stores/permissionGroups";
import storeUsers, { type User } from "@/stores/users";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { groupColor } from "@/v2/utils/groupColor";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const usersStore = storeUsers();
const { allUsers } = storeToRefs(usersStore);
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();
const groupsStore = storePermissionGroups();

const search = ref("");

type SortKey = "username" | "email" | "last_active" | "access";
const sortKey = ref<SortKey>("username");
const sortDir = ref<"asc" | "desc">("asc");

// Admins bypass groups; everyone else shows their group name. A user with no
// explicit group follows the server default group, so resolve to that.
function resolveGroup(user: User): PermissionGroupSchema | undefined {
  return (
    groupsStore.groups.find((x) => x.id === user.permission_group_id) ??
    groupsStore.defaultGroup
  );
}

function groupLabel(user: User): string {
  const g = resolveGroup(user);
  return g ? g.name : t("settings.group-default-option");
}

function groupPillColor(user: User): string {
  return groupColor(resolveGroup(user)?.color);
}

// The pill mirrors the admin RTag chrome (same shape/size) but tinted with
// the group's colour — override RTag's tone vars with the group hue.
function groupPillStyle(user: User) {
  const c = groupPillColor(user);
  return {
    "--r-tag-fg": `color-mix(in srgb, ${c} 90%, transparent)`,
    "--r-tag-border": `color-mix(in srgb, ${c} 40%, transparent)`,
    "--r-tag-bg": `color-mix(in srgb, ${c} 14%, transparent)`,
  };
}

// Sort key for the Access column: admins grouped under their label, others
// by their (resolved) group name.
function accessText(user: User): string {
  return user.role === "admin" ? t("settings.administrator") : groupLabel(user);
}

// Same nullable-string compare we use in ClientApiTokens — keeps users
// with no email / no last-active timestamp at the end on `asc`.
function compareNullable(
  a: string | null | undefined,
  b: string | null | undefined,
  asc: boolean,
) {
  if (!a && !b) return 0;
  if (!a) return asc ? 1 : -1;
  if (!b) return asc ? -1 : 1;
  return asc ? a.localeCompare(b) : b.localeCompare(a);
}

const sortedUsers = computed(() => {
  const list = [...allUsers.value];
  const asc = sortDir.value === "asc";
  list.sort((a, b) => {
    if (sortKey.value === "username") {
      return asc
        ? a.username.localeCompare(b.username)
        : b.username.localeCompare(a.username);
    }
    if (sortKey.value === "access") {
      return asc
        ? accessText(a).localeCompare(accessText(b))
        : accessText(b).localeCompare(accessText(a));
    }
    return compareNullable(a[sortKey.value], b[sortKey.value], asc);
  });
  return list;
});

const filteredUsers = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sortedUsers.value;
  return sortedUsers.value.filter(
    (u) =>
      u.username.toLowerCase().includes(q) ||
      (u.email ?? "").toLowerCase().includes(q),
  );
});

const columns = computed<RTableColumn[]>(() => [
  {
    key: "username",
    label: t("common.name"),
    sortable: true,
    width: "minmax(0, 1.4fr)",
    skeletonWidth: 160,
  },
  {
    key: "email",
    label: t("settings.email"),
    sortable: true,
    width: "minmax(0, 1.4fr)",
    skeletonWidth: 180,
  },
  {
    key: "access",
    label: t("settings.access"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "last_active",
    label: t("settings.users-last-active"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "enabled",
    label: t("settings.users-enabled"),
    width: "90px",
    align: "center",
    skeletonWidth: 40,
  },
  {
    key: "actions",
    label: "",
    width: "96px",
    align: "end",
    skeletonWidth: 0,
  },
]);

function onSort({ key, dir }: RTableSortPayload) {
  if (
    key !== "username" &&
    key !== "email" &&
    key !== "last_active" &&
    key !== "access"
  ) {
    return;
  }
  sortKey.value = key;
  sortDir.value = dir;
}

function avatarSrc(user: User) {
  return userAvatarUrl(user.avatar_path, user.updated_at);
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
    const detail =
      e?.response?.data?.detail || e?.response?.statusText || e?.message;
    snackbar.error(
      enabled
        ? t("settings.unable-to-enable-user", { detail })
        : t("settings.unable-to-disable-user", { detail }),
      { icon: "mdi-close-circle" },
    );
  }
}

async function deleteUser(user: User) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.delete-user-confirm", { username: user.username }),
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: user.username,
  });
  if (!ok) return;
  try {
    await userApi.deleteUser(user);
    usersStore.remove(user.id);
    snackbar.success(t("settings.user-removed", { username: user.username }), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.unable-to-delete-user", {
        username: user.username,
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  }
}

const loading = ref(true);

onMounted(async () => {
  try {
    const [usersResp] = await Promise.all([
      userApi.fetchUsers(),
      groupsStore.ensureLoaded(),
    ]);
    usersStore.set(usersResp.data);
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="r-v2-users">
    <RTextField
      v-model="search"
      prefix-label="inline"
      :placeholder="t('common.search')"
      hide-details
      density="compact"
      :aria-label="t('settings.search-users')"
      class="r-v2-users__search"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <RTable
      :columns="columns"
      :items="filteredUsers"
      :item-key="(r) => (r as User).id"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      :loading="loading"
      empty-icon="mdi-account-off-outline"
      :empty-message="t('settings.users-empty')"
      @update:sort="onSort"
    >
      <template #cell.username="{ row }">
        <div class="r-v2-users__name">
          <img
            :src="avatarSrc(row as User)"
            :alt="(row as User).username"
            class="r-v2-users__avatar"
          />
          <span>{{ (row as User).username }}</span>
        </div>
      </template>
      <template #cell.email="{ row }">
        <span class="r-v2-users__meta">{{ (row as User).email || "—" }}</span>
      </template>
      <template #cell.access="{ row }">
        <RTag
          v-if="(row as User).role === 'admin'"
          tone="brand"
          prepend-icon="mdi-shield-crown-outline"
          :text="t('settings.administrator')"
          class="r-v2-users__access-pill"
        />
        <RTag
          v-else
          :style="groupPillStyle(row as User)"
          :text="groupLabel(row as User)"
          class="r-v2-users__access-pill"
        />
      </template>
      <template #cell.last_active="{ row }">
        <span class="r-v2-users__meta">
          {{
            (row as User).last_active
              ? formatTimestamp((row as User).last_active!, locale)
              : "—"
          }}
        </span>
      </template>
      <template #cell.enabled="{ row }">
        <RSwitch
          :model-value="(row as User).enabled"
          :disabled="(row as User).id === auth.user?.id"
          :aria-label="
            (row as User).enabled
              ? t('settings.disable-user', { username: (row as User).username })
              : t('settings.enable-user', { username: (row as User).username })
          "
          @update:model-value="(v) => toggleEnabled(row as User, v)"
        />
      </template>
      <template #cell.actions="{ row }">
        <div class="r-v2-users__actions">
          <RTooltip>
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                variant="text"
                size="small"
                icon="mdi-pencil"
                :aria-label="t('settings.edit-user')"
                @click="emitter?.emit('showEditUserDialog', row as User)"
              />
            </template>
            <span>{{ t("settings.edit-user") }}</span>
          </RTooltip>
          <RTooltip>
            <template #activator="{ props: tipProps }">
              <RBtn
                v-bind="tipProps"
                variant="text"
                size="small"
                color="danger"
                icon="mdi-trash-can-outline"
                :disabled="(row as User).id === auth.user?.id"
                :aria-label="t('common.delete')"
                @click="deleteUser(row as User)"
              />
            </template>
            <span>{{ t("common.delete") }}</span>
          </RTooltip>
        </div>
      </template>
    </RTable>

    <div class="r-v2-users__footer">
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        @click="emitter?.emit('showCreateUserDialog', null)"
      >
        {{ t("common.add") }}
      </RBtn>
      <RBtn
        variant="text"
        prepend-icon="mdi-share-variant"
        @click="emitter?.emit('showCreateInviteLinkDialog')"
      >
        {{ t("settings.invite-link") }}
      </RBtn>
    </div>
  </div>
</template>

<style scoped>
.r-v2-users {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-users__name {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: var(--r-font-weight-semibold);
  min-width: 0;
}
.r-v2-users__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.r-v2-users__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* A touch more breathing room before the avatar (and matching header). */
.r-v2-users :deep(.r-table__header-cell:first-child),
.r-v2-users :deep(.r-table__cell:first-child) {
  padding-inline-start: 6px;
}
/* In the mobile card-stack that 6px indents the Name line past the other
   captions (Email / Access / …). Drop it so every caption shares the left
   edge; the row's own padding already provides the inset. */
html[data-bp~="xs"]
  .r-v2-users
  :deep(.r-table--mobile-stack .r-table__cell:first-child) {
  padding-inline-start: 0;
}

/* Keep the admin pill the same height as the icon-less group pills — the
   prepend icon's vertical margin would otherwise make it a touch taller. */
.r-v2-users :deep(.r-v2-users__access-pill .r-tag__icon) {
  margin-block: 0;
}

.r-v2-users__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.r-v2-users__footer {
  display: flex;
  justify-content: flex-start;
  gap: 10px;
}
</style>
