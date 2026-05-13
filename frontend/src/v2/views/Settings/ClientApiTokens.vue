<script setup lang="ts">
// ClientApiTokens — v2-native rewrite. Page chrome mirrors the mock:
// title + Create button on the right, search bar, single bordered table.
// Delete confirmation goes through useConfirm; create + regenerate are
// handled by the multi-step CreateClientTokenDialog component.
import { RBtn, RIcon, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import type { Events } from "@/types/emitter";
import { formatTimestamp } from "@/utils";
import CreateClientTokenDialog from "@/v2/components/Settings/CreateClientTokenDialog.vue";
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

const filteredTokens = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return tokens.value;
  return tokens.value.filter(
    (t) =>
      t.name.toLowerCase().includes(q) ||
      t.scopes.some((s) => s.toLowerCase().includes(q)),
  );
});

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
    <header class="r-v2-tok__head">
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-plus"
        @click="openCreate"
      >
        {{ t("common.create") }}
      </RBtn>
    </header>

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

    <div class="r-v2-table-wrap">
      <table class="r-v2-table">
        <thead>
          <tr>
            <th>{{ t("common.name") }}</th>
            <th>{{ t("settings.client-token-scopes") }}</th>
            <th>Expires</th>
            <th>Last used</th>
            <th class="r-v2-table__col-actions" />
          </tr>
        </thead>
        <tbody>
          <tr v-for="token in filteredTokens" :key="token.id">
            <td class="r-v2-tok__name">{{ token.name }}</td>
            <td class="r-v2-tok__scopes">
              <span
                v-for="scope in token.scopes"
                :key="scope"
                class="r-v2-tok__scope"
              >
                {{ scope }}
              </span>
            </td>
            <td class="r-v2-tok__meta">
              {{
                token.expires_at
                  ? formatTimestamp(token.expires_at, locale)
                  : t("settings.client-token-expiry-never")
              }}
            </td>
            <td class="r-v2-tok__meta">
              {{
                token.last_used_at
                  ? formatTimestamp(token.last_used_at, locale)
                  : "—"
              }}
            </td>
            <td class="r-v2-table__col-actions">
              <button
                type="button"
                class="r-v2-icon-btn"
                title="Regenerate"
                aria-label="Regenerate token"
                @click="openRegenerate(token)"
              >
                <RIcon icon="mdi-refresh" size="14" />
              </button>
              <button
                type="button"
                class="r-v2-icon-btn r-v2-icon-btn--danger"
                :title="t('common.delete')"
                :aria-label="t('common.delete')"
                @click="deleteToken(token)"
              >
                <RIcon icon="mdi-trash-can-outline" size="14" />
              </button>
            </td>
          </tr>
          <tr v-if="!loading && filteredTokens.length === 0">
            <td colspan="5" class="r-v2-tok__empty">
              No tokens — create one to start pairing devices.
            </td>
          </tr>
        </tbody>
      </table>
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

.r-v2-table-wrap {
  border: 1px solid var(--r-color-border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--r-color-bg-elevated);
}
.r-v2-table {
  width: 100%;
  border-collapse: collapse;
}
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
  padding: 12px 14px;
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
.r-v2-icon-btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-icon-btn--danger {
  color: color-mix(in srgb, var(--r-color-danger) 70%, transparent);
}
.r-v2-icon-btn--danger:hover {
  background: color-mix(in srgb, var(--r-color-danger) 12%, transparent);
  color: var(--r-color-danger);
}

.r-v2-tok__name {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
}
.r-v2-tok__scopes {
  max-width: 320px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.r-v2-tok__scope {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-tok__meta {
  white-space: nowrap;
  color: var(--r-color-fg-muted);
}
.r-v2-tok__empty {
  text-align: center;
  color: var(--r-color-fg-muted);
  padding: 24px 16px;
}

.r-v2-tok-dialog {
  display: contents;
}
</style>
