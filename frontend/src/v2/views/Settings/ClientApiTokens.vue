<script setup lang="ts">
// ClientApiTokens — v2-native rewrite. Page chrome mirrors the mock:
// title + Create button on the right, search bar, single RTable.
//
// Delete confirmation goes through useConfirm; create + regenerate are
// handled by the multi-step CreateClientTokenDialog component.
//
// Scopes are rendered through ScopeTree so the row groups them by
// scope instead of dumping flat chips — easier to scan when a token
// carries the full grant set.
import {
  RBtn,
  RIcon,
  RTable,
  RTextField,
  type RTableColumn,
  type RTableSortPayload,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";
import CreateClientTokenDialog from "@/v2/components/Settings/CreateClientTokenDialog.vue";
import ScopeCell from "@/v2/components/Settings/ScopeCell.vue";
import SettingsShell from "@/v2/components/Settings/SettingsShell.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t, locale } = useI18n();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();
const confirm = useConfirm();

const tokens = ref<ClientTokenSchema[]>([]);
const search = ref("");
const loading = ref(false);

type SortKey = "name" | "expires_at" | "last_used_at";
const sortKey = ref<SortKey>("name");
const sortDir = ref<"asc" | "desc">("asc");

// Null timestamps sort to the end on asc, start on desc — matches the
// "never expires" / "never used" reading: rows with values come first
// when sorting ascending by date.
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
      t.name.toLowerCase().includes(q) ||
      t.scopes.some((s) => s.toLowerCase().includes(q)),
  );
});

const columns = computed<RTableColumn[]>(() => [
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
    label: "Expires",
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
  },
  {
    key: "last_used_at",
    label: "Last used",
    sortable: true,
    width: "minmax(0, 1fr)",
    skeletonWidth: 110,
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
  if (key !== "name" && key !== "expires_at" && key !== "last_used_at") return;
  sortKey.value = key;
  sortDir.value = dir;
}

async function fetchTokens() {
  loading.value = true;
  try {
    const { data } = await clientTokenApi.fetchTokens();
    tokens.value = data;
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  emitter?.emit("showCreateClientTokenDialog", null);
}

function openRegenerate(token: ClientTokenSchema) {
  emitter?.emit("showRegenerateClientTokenDialog", token);
}

async function deleteToken(token: ClientTokenSchema) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.client-token-confirm-delete"),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await clientTokenApi.deleteToken(token.id);
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
      `Unable to delete token: ${e?.response?.data?.detail || e?.response?.statusText || e?.message}`,
      { icon: "mdi-close-circle" },
    );
  }
}

onMounted(fetchTokens);
</script>

<template>
  <SettingsShell bare>
    <RTextField
      v-model="search"
      prefix-label="inline"
      :placeholder="t('common.search')"
      hide-details
      density="compact"
      aria-label="Search tokens"
      class="r-v2-tok__search"
    >
      <template #prefix-label>
        <RIcon icon="mdi-magnify" size="15" />
      </template>
    </RTextField>

    <RTable
      :columns="columns"
      :items="filteredTokens"
      :item-key="(r) => (r as ClientTokenSchema).id"
      :sort-key="sortKey"
      :sort-dir="sortDir"
      :loading="loading"
      empty-icon="mdi-key-outline"
      empty-message="No tokens — create one to start pairing devices."
      class="r-v2-tok__table"
      @update:sort="onSort"
    >
      <template #cell.name="{ row }">
        <span class="r-v2-tok__name">{{
          (row as ClientTokenSchema).name
        }}</span>
      </template>
      <template #cell.scopes="{ row }">
        <ScopeCell :scopes="(row as ClientTokenSchema).scopes" />
      </template>
      <template #cell.expires_at="{ row }">
        <span class="r-v2-tok__meta">
          {{
            (row as ClientTokenSchema).expires_at
              ? formatTimestamp((row as ClientTokenSchema).expires_at!, locale)
              : t("settings.client-token-expiry-never")
          }}
        </span>
      </template>
      <template #cell.last_used_at="{ row }">
        <span class="r-v2-tok__meta">
          {{
            (row as ClientTokenSchema).last_used_at
              ? formatTimestamp(
                  (row as ClientTokenSchema).last_used_at!,
                  locale,
                )
              : "—"
          }}
        </span>
      </template>
      <template #cell.actions="{ row }">
        <div class="r-v2-tok__actions">
          <RBtn
            variant="text"
            size="small"
            icon="mdi-refresh"
            aria-label="Regenerate token"
            title="Regenerate"
            @click="openRegenerate(row as ClientTokenSchema)"
          />
          <RBtn
            variant="text"
            size="small"
            icon="mdi-trash-can-outline"
            color="danger"
            :aria-label="t('common.delete')"
            :title="t('common.delete')"
            class="r-v2-tok__delete"
            @click="deleteToken(row as ClientTokenSchema)"
          />
        </div>
      </template>
    </RTable>
    <div>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openCreate"
      >
        {{ t("common.create") }}
      </RBtn>
    </div>

    <CreateClientTokenDialog @created="fetchTokens" />
  </SettingsShell>
</template>

<style scoped>
.r-v2-tok__head {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 16px;
  gap: 12px;
}

.r-v2-tok__search {
  margin-bottom: 16px;
}

.r-v2-tok__name {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-tok__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
}

.r-v2-tok__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* Dimmed at rest, full red on hover. RBtn's text variant uses
   `var(--r-btn-color)` for the icon colour; setting that token directly
   on the button root drives both states without a :deep selector. */
.r-v2-tok__delete {
  --r-btn-color: color-mix(in srgb, var(--r-color-danger) 70%, transparent);
}
.r-v2-tok__delete:hover {
  --r-btn-color: var(--r-color-danger);
}
</style>
