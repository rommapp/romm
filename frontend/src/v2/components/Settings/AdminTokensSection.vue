<script setup lang="ts">
// AdminTokensSection — v2-native rebuild of v1
// `Settings/Administration/Tokens/TokensTable.vue`. Shows every client
// token across all users (admin scope). Admins can revoke any.
//
// Not in the mock — kept here because it's a useful safety surface.
// Visual matches the same settings-table pattern used elsewhere.
import { RIcon, RTextField, RTooltip } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import clientTokenApi, {
  type ClientTokenAdminSchema,
} from "@/services/api/client-token";
import { formatTimestamp } from "@/utils";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();

const tokens = ref<ClientTokenAdminSchema[]>([]);
const search = ref("");

const filteredTokens = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return tokens.value;
  return tokens.value.filter(
    (t) =>
      t.username.toLowerCase().includes(q) ||
      t.name.toLowerCase().includes(q) ||
      t.scopes.some((s) => s.toLowerCase().includes(q)),
  );
});

async function fetchTokens() {
  try {
    const { data } = await clientTokenApi.fetchAllTokens();
    tokens.value = data;
  } catch (err) {
    console.error(err);
  }
}

async function revoke(token: ClientTokenAdminSchema) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: `Revoke token "${token.name}" for ${token.username}?`,
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
      `Unable to revoke token: ${
        e?.response?.data?.detail || e?.response?.statusText || e?.message
      }`,
      { icon: "mdi-close-circle" },
    );
  }
}

onMounted(fetchTokens);
</script>

<template>
  <SettingsSection title="Client API tokens (all users)" icon="mdi-key-variant">
    <div class="r-v2-admin-tokens__search">
      <RTextField
        v-model="search"
        prefix-label="inline"
        :placeholder="t('common.search')"
        hide-details
        density="compact"
        aria-label="Search tokens"
      >
        <template #prefix-label>
          <RIcon icon="mdi-magnify" size="15" />
        </template>
      </RTextField>
    </div>
    <table class="r-v2-table r-v2-admin-tokens__table">
      <thead>
        <tr>
          <th>User</th>
          <th>Token name</th>
          <th>{{ t("settings.client-token-scopes") }}</th>
          <th>Expires</th>
          <th>Last used</th>
          <th class="r-v2-table__col-actions" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="token in filteredTokens" :key="token.id">
          <td class="r-v2-admin-tokens__user">{{ token.username }}</td>
          <td class="r-v2-admin-tokens__name">{{ token.name }}</td>
          <td class="r-v2-admin-tokens__scopes">
            <span
              v-for="scope in token.scopes"
              :key="scope"
              class="r-v2-admin-tokens__scope"
            >
              {{ scope }}
            </span>
          </td>
          <td class="r-v2-admin-tokens__meta">
            {{
              token.expires_at
                ? formatTimestamp(token.expires_at, locale)
                : t("settings.client-token-expiry-never")
            }}
          </td>
          <td class="r-v2-admin-tokens__meta">
            {{
              token.last_used_at
                ? formatTimestamp(token.last_used_at, locale)
                : "—"
            }}
          </td>
          <td class="r-v2-table__col-actions">
            <RTooltip>
              <template #activator="{ props: tipProps }">
                <button
                  v-bind="tipProps"
                  type="button"
                  class="r-v2-icon-btn r-v2-icon-btn--danger"
                  :aria-label="t('common.delete')"
                  @click="revoke(token)"
                >
                  <RIcon icon="mdi-trash-can-outline" size="14" />
                </button>
              </template>
              <span>{{ t("common.delete") }}</span>
            </RTooltip>
          </td>
        </tr>
        <tr v-if="filteredTokens.length === 0">
          <td colspan="6" class="r-v2-admin-tokens__empty">No tokens.</td>
        </tr>
      </tbody>
    </table>
  </SettingsSection>
</template>

<style scoped>
.r-v2-admin-tokens__search {
  padding: 12px 14px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-admin-tokens__table {
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

.r-v2-admin-tokens__user {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
}
.r-v2-admin-tokens__name {
  white-space: nowrap;
}
.r-v2-admin-tokens__scopes {
  max-width: 320px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.r-v2-admin-tokens__scope {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border);
  font-size: 10px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-admin-tokens__meta {
  color: var(--r-color-fg-muted);
  white-space: nowrap;
}
.r-v2-admin-tokens__empty {
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
</style>
