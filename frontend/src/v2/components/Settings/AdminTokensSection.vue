<script setup lang="ts">
// AdminTokensSection — admin variant of ClientApiTokens. Same table
// shape (RTable + ScopeCell summary chip + delete confirm), but the
// data comes from `/client-tokens/all` so every user's tokens land in
// the same list. Adds a leading `User` column and drops the
// regenerate action — admins can only revoke; rotating a credential
// still belongs to the owner via the user-facing ClientApiTokens view.
//
// No "Create" CTA either — admins create their own tokens through
// their personal Client API tokens page, not here.
import {
  RBtn,
  RIcon,
  RTable,
  RTextField,
  RTooltip,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import clientTokenApi, {
  type ClientTokenAdminSchema,
} from "@/services/api/client-token";
import { formatTimestamp } from "@/utils";
import ScopeCell from "@/v2/components/Settings/ScopeCell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { userAvatarUrl } from "@/v2/utils/userAvatar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();

const tokens = ref<ClientTokenAdminSchema[]>([]);
const search = ref("");
const loading = ref(true);

type SortKey = "username" | "name" | "expires_at" | "last_used_at";
const sortKey = ref<SortKey>("username");
const sortDir = ref<"asc" | "desc">("asc");

function avatarSrc(token: ClientTokenAdminSchema) {
  return userAvatarUrl({
    userId: token.user_id,
    avatarPath: token.user_avatar_path,
    updatedAt: token.user_updated_at,
  });
}

function compareNullable(a: string | null, b: string | null, asc: boolean) {
  if (!a && !b) return 0;
  if (!a) return asc ? 1 : -1;
  if (!b) return asc ? -1 : 1;
  return asc ? a.localeCompare(b) : b.localeCompare(a);
}

const sortedTokens = computed(() => {
  const list = [...tokens.value];
  const asc = sortDir.value === "asc";
  list.sort((a, b) => {
    if (sortKey.value === "username") {
      return asc
        ? a.username.localeCompare(b.username) || a.name.localeCompare(b.name)
        : b.username.localeCompare(a.username) || b.name.localeCompare(a.name);
    }
    if (sortKey.value === "name") {
      return asc ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    }
    return compareNullable(a[sortKey.value], b[sortKey.value], asc);
  });
  return list;
});

const filteredTokens = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sortedTokens.value;
  return sortedTokens.value.filter(
    (t) =>
      t.username.toLowerCase().includes(q) ||
      t.name.toLowerCase().includes(q) ||
      t.scopes.some((s) => s.toLowerCase().includes(q)),
  );
});

const columns = computed<RTableColumn[]>(() => [
  {
    key: "username",
    label: t("settings.tokens-admin-table-user"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 120,
  },
  {
    key: "name",
    label: t("common.name"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 140,
  },
  {
    key: "scopes",
    label: t("settings.client-token-scopes"),
    width: "minmax(0, 2fr)",
    skeletonWidth: 220,
  },
  {
    key: "expires_at",
    label: t("settings.users-tokens-expires"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "last_used_at",
    label: t("settings.users-tokens-last-used"),
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "actions",
    label: "",
    width: "56px",
    align: "end",
    skeletonWidth: 0,
  },
]);

function onSort({ key, dir }: RTableSortPayload) {
  if (
    key !== "username" &&
    key !== "name" &&
    key !== "expires_at" &&
    key !== "last_used_at"
  ) {
    return;
  }
  sortKey.value = key;
  sortDir.value = dir;
}

async function fetchTokens() {
  loading.value = true;
  try {
    const { data } = await clientTokenApi.fetchAllTokens();
    tokens.value = data;
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
}

async function revoke(token: ClientTokenAdminSchema) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.revoke-token-confirm", {
      name: token.name,
      username: token.username,
    }),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await clientTokenApi.adminDeleteToken(token.id);
    tokens.value = tokens.value.filter((t) => t.id !== token.id);
    snackbar.success(t("settings.client-token-deleted"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      t("settings.unable-to-revoke-token", {
        detail:
          e?.response?.data?.detail || e?.response?.statusText || e?.message,
      }),
      { icon: "mdi-close-circle" },
    );
  }
}

onMounted(fetchTokens);
</script>

<template>
  <div class="r-v2-admin-tokens">
    <RTextField
      v-model="search"
      prefix-label="inline"
      :placeholder="t('common.search')"
      hide-details
      density="compact"
      :aria-label="t('settings.search-tokens')"
      class="r-v2-admin-tokens__search"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <RTable
      :columns="columns"
      :items="filteredTokens"
      :item-key="(r) => (r as ClientTokenAdminSchema).id"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      :loading="loading"
      empty-icon="mdi-key-outline"
      :empty-message="t('settings.tokens-admin-empty')"
      @update:sort="onSort"
    >
      <template #cell.username="{ row }">
        <div class="r-v2-admin-tokens__user">
          <img
            :src="avatarSrc(row as ClientTokenAdminSchema)"
            :alt="(row as ClientTokenAdminSchema).username"
            class="r-v2-admin-tokens__avatar"
          />
          <span>{{ (row as ClientTokenAdminSchema).username }}</span>
        </div>
      </template>
      <template #cell.name="{ row }">
        <span class="r-v2-admin-tokens__name">{{
          (row as ClientTokenAdminSchema).name
        }}</span>
      </template>
      <template #cell.scopes="{ row }">
        <ScopeCell :scopes="(row as ClientTokenAdminSchema).scopes" />
      </template>
      <template #cell.expires_at="{ row }">
        <span class="r-v2-admin-tokens__meta">
          {{
            (row as ClientTokenAdminSchema).expires_at
              ? formatTimestamp(
                  (row as ClientTokenAdminSchema).expires_at!,
                  locale,
                )
              : t("settings.client-token-expiry-never")
          }}
        </span>
      </template>
      <template #cell.last_used_at="{ row }">
        <span class="r-v2-admin-tokens__meta">
          {{
            (row as ClientTokenAdminSchema).last_used_at
              ? formatTimestamp(
                  (row as ClientTokenAdminSchema).last_used_at!,
                  locale,
                )
              : "—"
          }}
        </span>
      </template>
      <template #cell.actions="{ row }">
        <RTooltip>
          <template #activator="{ props: tipProps }">
            <RBtn
              v-bind="tipProps"
              variant="text"
              size="small"
              color="danger"
              icon="mdi-trash-can-outline"
              :aria-label="t('common.delete')"
              @click="revoke(row as ClientTokenAdminSchema)"
            />
          </template>
          <span>{{ t("common.delete") }}</span>
        </RTooltip>
      </template>
    </RTable>
  </div>
</template>

<style scoped>
.r-v2-admin-tokens {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.r-v2-admin-tokens__user {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: var(--r-font-weight-semibold);
  min-width: 0;
}
.r-v2-admin-tokens__user span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-admin-tokens__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}

.r-v2-admin-tokens__name {
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-admin-tokens__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
}
</style>
