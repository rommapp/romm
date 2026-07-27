<script setup lang="ts">
import {
  RBtn,
  RForm,
  RIcon,
  RTable,
  RTag,
  RTextField,
  RTooltip,
  type RTableColumn,
} from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import type {
  PlatformSchema,
  SmbAccessMode,
  SmbStatusSchema,
  SmbUserSchema,
  SmbUserSecretSchema,
} from "@/__generated__";
import platformApi from "@/services/api/platform";
import smbApi, { type SmbPermissionInput } from "@/services/api/smb";
import { useClipboard } from "@/v2/composables/useClipboard";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const clipboard = useClipboard();
const confirm = useConfirm();
const snackbar = useSnackbar();

const statusInfo = ref<SmbStatusSchema | null>(null);
const users = ref<SmbUserSchema[]>([]);
const platforms = ref<PlatformSchema[]>([]);
const loading = ref(true);
const submitting = ref(false);
const rotatingUserId = ref<number | null>(null);
const serviceAction = ref<"start" | "restart" | null>(null);
const logsLoading = ref(false);
const showLogs = ref(false);
const logLines = ref<string[]>([]);

const showForm = ref(false);
const editingUser = ref<SmbUserSchema | null>(null);
const username = ref("");
const platformSearch = ref("");
const accessByPlatform = ref<Record<number, SmbAccessMode | undefined>>({});
const formRef = ref<{ validate: () => Promise<{ valid: boolean }> } | null>(
  null,
);

const showCredential = ref(false);
const credentialUserId = ref<number | null>(null);
const credentialVisible = ref(false);
const credentialsByUser = ref<Record<number, SmbUserSecretSchema>>({});

const credential = computed(() =>
  credentialUserId.value === null
    ? null
    : credentialsByUser.value[credentialUserId.value] || null,
);

const connectionHost = computed(
  () => statusInfo.value?.advertised_host || window.location.hostname,
);
const connectionAddress = computed(() => `\\\\${connectionHost.value}`);
const connectionUri = computed(() => {
  const port = statusInfo.value?.advertised_port || 445;
  const host = connectionHost.value.includes(":")
    ? `[${connectionHost.value.replace(/^\[|\]$/g, "")}]`
    : connectionHost.value;
  return `smb://${host}${port === 445 ? "" : `:${port}`}`;
});

const columns = computed<RTableColumn[]>(() => [
  {
    key: "username",
    label: t("settings.smb-username"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 140,
  },
  {
    key: "permissions",
    label: t("settings.smb-platform-access"),
    width: "minmax(0, 3fr)",
    skeletonWidth: 240,
  },
  {
    key: "actions",
    label: "",
    width: "430px",
    align: "end",
    skeletonWidth: 0,
  },
]);

const sortedPlatforms = computed(() =>
  [...platforms.value]
    .filter((platform) => !platform.missing_from_fs)
    .sort((a, b) => a.display_name.localeCompare(b.display_name)),
);

const filteredPlatforms = computed(() => {
  const query = platformSearch.value.trim().toLocaleLowerCase();
  if (!query) return sortedPlatforms.value;
  return sortedPlatforms.value.filter((platform) =>
    platform.display_name.toLocaleLowerCase().includes(query),
  );
});

const selectedPlatformCount = computed(
  () =>
    sortedPlatforms.value.filter((platform) =>
      Boolean(accessByPlatform.value[platform.id]),
    ).length,
);

const selectedPermissions = computed<SmbPermissionInput[]>(() =>
  Object.entries(accessByPlatform.value)
    .filter((entry): entry is [string, SmbAccessMode] =>
      Boolean(entry[1] === "read" || entry[1] === "write"),
    )
    .map(([platformId, access]) => ({
      platform_id: Number(platformId),
      access,
    })),
);

function errorDetail(error: unknown): string {
  const value = error as {
    response?: { data?: { detail?: string }; statusText?: string };
    message?: string;
  };
  return (
    value.response?.data?.detail ||
    value.response?.statusText ||
    value.message ||
    t("settings.smb-unknown-error")
  );
}

async function fetchData() {
  loading.value = true;
  try {
    const [statusResponse, usersResponse, platformsResponse] =
      await Promise.all([
        smbApi.getStatus(),
        smbApi.getUsers(),
        platformApi.getPlatforms(),
      ]);
    statusInfo.value = statusResponse.data;
    users.value = usersResponse.data;
    platforms.value = platformsResponse.data;
  } catch (error) {
    snackbar.error(
      t("settings.smb-load-failed", { detail: errorDetail(error) }),
    );
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingUser.value = null;
  username.value = "";
  platformSearch.value = "";
  accessByPlatform.value = {};
  showForm.value = true;
}

function openEdit(user: SmbUserSchema) {
  editingUser.value = user;
  username.value = user.username;
  platformSearch.value = "";
  accessByPlatform.value = Object.fromEntries(
    user.permissions.map((permission) => [
      permission.platform_id,
      permission.access,
    ]),
  );
  showForm.value = true;
}

function setPlatformAccess(platformId: number, value: string) {
  const next = { ...accessByPlatform.value };
  if (value === "read" || value === "write") next[platformId] = value;
  else delete next[platformId];
  accessByPlatform.value = next;
}

function setAllPlatformAccess(access?: SmbAccessMode) {
  if (!access) {
    accessByPlatform.value = {};
    return;
  }
  accessByPlatform.value = Object.fromEntries(
    sortedPlatforms.value.map((platform) => [platform.id, access]),
  );
}

function permissionLabel(access: SmbAccessMode): string {
  return access === "write" ? t("settings.smb-write") : t("settings.smb-read");
}

async function saveUser() {
  if (submitting.value) return;
  const validation = await formRef.value?.validate();
  if (!validation?.valid) return;
  if (selectedPermissions.value.length === 0) {
    snackbar.warning(t("settings.smb-select-platform"));
    return;
  }

  submitting.value = true;
  try {
    if (editingUser.value) {
      const { data } = await smbApi.updateUser(
        editingUser.value.id,
        selectedPermissions.value,
      );
      users.value = users.value.map((user) =>
        user.id === data.id ? data : user,
      );
      snackbar.success(
        t("settings.smb-user-updated", { username: data.username }),
      );
    } else {
      const { data } = await smbApi.createUser({
        username: username.value.trim().toLowerCase(),
        permissions: selectedPermissions.value,
      });
      const { password: _password, ...user } = data;
      users.value = [...users.value, user].sort((a, b) =>
        a.username.localeCompare(b.username),
      );
      credentialsByUser.value = {
        ...credentialsByUser.value,
        [data.id]: data,
      };
      credentialUserId.value = data.id;
      credentialVisible.value = false;
      showCredential.value = true;
      snackbar.success(
        t("settings.smb-user-created", { username: data.username }),
      );
    }
    showForm.value = false;
    await refreshStatus();
  } catch (error) {
    snackbar.error(
      t("settings.smb-save-failed", { detail: errorDetail(error) }),
    );
  } finally {
    submitting.value = false;
  }
}

async function rotateUser(user: SmbUserSchema) {
  if (rotatingUserId.value !== null) return;
  const accepted = await confirm({
    title: t("settings.smb-rotate-title"),
    body: t("settings.smb-rotate-confirm", { username: user.username }),
    confirmText: t("settings.smb-rotate"),
    tone: "warning",
  });
  if (!accepted) return;
  rotatingUserId.value = user.id;
  try {
    const { data } = await smbApi.rotateUser(user.id);
    credentialsByUser.value = {
      ...credentialsByUser.value,
      [data.id]: data,
    };
    credentialUserId.value = data.id;
    credentialVisible.value = false;
    showCredential.value = true;
    snackbar.success(
      t("settings.smb-user-rotated", { username: user.username }),
    );
  } catch (error) {
    snackbar.error(
      t("settings.smb-save-failed", { detail: errorDetail(error) }),
    );
  } finally {
    rotatingUserId.value = null;
  }
}

async function deleteUser(user: SmbUserSchema) {
  const accepted = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.smb-delete-confirm", { username: user.username }),
    confirmText: t("common.delete"),
    tone: "danger",
    requireTyped: user.username,
  });
  if (!accepted) return;
  try {
    await smbApi.deleteUser(user.id);
    users.value = users.value.filter((candidate) => candidate.id !== user.id);
    const nextCredentials = { ...credentialsByUser.value };
    delete nextCredentials[user.id];
    credentialsByUser.value = nextCredentials;
    snackbar.success(
      t("settings.smb-user-deleted", { username: user.username }),
    );
    await refreshStatus();
  } catch (error) {
    snackbar.error(
      t("settings.smb-delete-failed", { detail: errorDetail(error) }),
    );
  }
}

async function refreshStatus() {
  const { data } = await smbApi.getStatus();
  statusInfo.value = data;
}

async function syncConfig() {
  try {
    await smbApi.syncConfig();
    await refreshStatus();
    snackbar.success(t("settings.smb-synced"));
  } catch (error) {
    snackbar.error(
      t("settings.smb-sync-failed", { detail: errorDetail(error) }),
    );
  }
}

function showSavedCredential(user: SmbUserSchema) {
  const savedCredential = credentialsByUser.value[user.id];
  if (!savedCredential) return;
  credentialUserId.value = savedCredential.id;
  credentialVisible.value = false;
  showCredential.value = true;
}

function closeCredential() {
  showCredential.value = false;
  credentialUserId.value = null;
  credentialVisible.value = false;
}

async function startOrRestartService() {
  const action = statusInfo.value?.samba_running ? "restart" : "start";
  serviceAction.value = action;
  try {
    const { data } =
      action === "restart"
        ? await smbApi.restartService()
        : await smbApi.startService();
    statusInfo.value = data;
    snackbar.success(
      t(
        action === "restart"
          ? "settings.smb-service-restarted"
          : "settings.smb-service-started",
      ),
    );
  } catch (error) {
    snackbar.error(
      t("settings.smb-service-failed", { detail: errorDetail(error) }),
    );
    await refreshStatus().catch(() => undefined);
  } finally {
    serviceAction.value = null;
  }
}

async function refreshLogs() {
  logsLoading.value = true;
  try {
    const { data } = await smbApi.getLogs();
    logLines.value = data.lines;
  } catch (error) {
    snackbar.error(
      t("settings.smb-logs-failed", { detail: errorDetail(error) }),
    );
  } finally {
    logsLoading.value = false;
  }
}

async function openLogs() {
  showLogs.value = true;
  await refreshLogs();
}

async function copyConnectionAddress() {
  await clipboard.copy(connectionUri.value, {
    successMessage: t("settings.smb-address-copied"),
  });
}

function formatStartedAt(value?: string | null): string {
  if (!value) return t("settings.smb-not-available");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t("settings.smb-not-available");
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

async function copyPassword() {
  if (!credential.value) return;
  await clipboard.copy(credential.value.password, {
    successMessage: t("settings.smb-password-copied"),
  });
}

onMounted(fetchData);
</script>

<template>
  <div class="r-v2-smb">
    <div class="r-v2-smb__header">
      <div>
        <div class="r-v2-smb__title-row">
          <RIcon icon="mdi-folder-network-outline" size="20" />
          <h3>{{ t("settings.smb-access") }}</h3>
          <RTag
            v-if="statusInfo"
            :tone="statusInfo.samba_running ? 'success' : 'danger'"
            :text="
              statusInfo.samba_running
                ? t('settings.smb-service-running')
                : statusInfo.controller_online
                  ? t('settings.smb-service-stopped')
                  : t('settings.smb-controller-offline')
            "
            size="small"
          />
        </div>
        <p>{{ t("settings.smb-description") }}</p>
      </div>
      <div class="r-v2-smb__header-actions">
        <RBtn
          variant="text"
          prepend-icon="mdi-text-box-search-outline"
          :disabled="!statusInfo?.controller_online"
          @click="openLogs"
        >
          {{ t("settings.smb-view-logs") }}
        </RBtn>
        <RBtn
          variant="outlined"
          :prepend-icon="
            statusInfo?.samba_running ? 'mdi-restart' : 'mdi-play-outline'
          "
          :loading="Boolean(serviceAction)"
          :disabled="statusInfo?.enabled === false"
          @click="startOrRestartService"
        >
          {{
            statusInfo?.samba_running
              ? t("settings.smb-restart-service")
              : t("settings.smb-start-service")
          }}
        </RBtn>
        <RBtn
          variant="text"
          prepend-icon="mdi-sync"
          :disabled="!statusInfo?.samba_running"
          @click="syncConfig"
        >
          {{ t("settings.smb-sync") }}
        </RBtn>
        <RBtn
          variant="flat"
          prepend-icon="mdi-account-plus"
          :disabled="!statusInfo?.samba_running"
          @click="openCreate"
        >
          {{ t("settings.smb-new-user") }}
        </RBtn>
      </div>
    </div>

    <p v-if="statusInfo && !statusInfo.enabled" class="r-v2-smb__warning">
      <RIcon icon="mdi-alert-outline" size="17" />
      {{ t("settings.smb-disabled") }}
    </p>

    <section v-if="statusInfo" class="r-v2-smb__server-panel">
      <div class="r-v2-smb__server-heading">
        <div>
          <strong>{{ t("settings.smb-server-details") }}</strong>
          <span>{{ t("settings.smb-server-details-hint") }}</span>
        </div>
        <RBtn
          variant="text"
          size="small"
          prepend-icon="mdi-content-copy"
          @click="copyConnectionAddress"
        >
          {{ t("settings.smb-copy-address") }}
        </RBtn>
      </div>
      <div class="r-v2-smb__server-grid">
        <div>
          <span>{{ t("settings.smb-address") }}</span>
          <code>{{ connectionAddress }}</code>
          <small>{{ connectionUri }}</small>
        </div>
        <div>
          <span>{{ t("settings.smb-port") }}</span>
          <strong>{{ statusInfo.advertised_port }}</strong>
        </div>
        <div>
          <span>{{ t("settings.smb-workgroup") }}</span>
          <strong>{{ statusInfo.workgroup }}</strong>
        </div>
        <div>
          <span>{{ t("settings.smb-version") }}</span>
          <strong>{{
            statusInfo.samba_version || t("settings.smb-not-available")
          }}</strong>
        </div>
        <div>
          <span>{{ t("settings.smb-started-at") }}</span>
          <strong>{{ formatStartedAt(statusInfo.started_at) }}</strong>
        </div>
      </div>
      <p
        v-if="!statusInfo.controller_online"
        class="r-v2-smb__service-note"
      >
        <RIcon icon="mdi-information-outline" size="18" />
        {{ t("settings.smb-container-unavailable") }}
      </p>
    </section>

    <RTable
      :columns="columns"
      :items="users"
      :item-key="(row) => (row as SmbUserSchema).id"
      :loading="loading"
      empty-icon="mdi-account-network-outline"
      :empty-message="t('settings.smb-users-empty')"
    >
      <template #cell.username="{ row }">
        <strong>{{ (row as SmbUserSchema).username }}</strong>
      </template>
      <template #cell.permissions="{ row }">
        <div class="r-v2-smb__permissions">
          <RTag
            v-for="permission in (row as SmbUserSchema).permissions"
            :key="permission.platform_id"
            :tone="permission.access === 'write' ? 'warning' : 'info'"
            :prepend-icon="
              permission.access === 'write'
                ? 'mdi-pencil-outline'
                : 'mdi-eye-outline'
            "
            :text="`${permission.platform_name} · ${permissionLabel(permission.access)}`"
            size="small"
          />
        </div>
      </template>
      <template #cell.actions="{ row }">
        <div class="r-v2-smb__actions">
          <RTooltip :text="t('common.edit')" location="top">
            <template #activator="{ props: tooltipProps }">
              <RBtn
                v-bind="tooltipProps"
                prepend-icon="mdi-pencil-outline"
                variant="text"
                size="small"
                :aria-label="t('common.edit')"
                @click="openEdit(row as SmbUserSchema)"
              >
                {{ t("common.edit") }}
              </RBtn>
            </template>
          </RTooltip>
          <RTooltip :text="t('settings.smb-rotate')" location="top">
            <template #activator="{ props: tooltipProps }">
              <RBtn
                v-bind="tooltipProps"
                prepend-icon="mdi-key-change"
                variant="text"
                size="small"
                :loading="rotatingUserId === (row as SmbUserSchema).id"
                :disabled="rotatingUserId !== null"
                :aria-label="t('settings.smb-rotate')"
                @click="rotateUser(row as SmbUserSchema)"
              >
                {{ t("settings.smb-rotate") }}
              </RBtn>
            </template>
          </RTooltip>
          <RTooltip
            v-if="credentialsByUser[(row as SmbUserSchema).id]"
            :text="t('settings.smb-view-password')"
            location="top"
          >
            <template #activator="{ props: tooltipProps }">
              <RBtn
                v-bind="tooltipProps"
                prepend-icon="mdi-eye-outline"
                variant="text"
                size="small"
                :aria-label="t('settings.smb-view-password')"
                @click="showSavedCredential(row as SmbUserSchema)"
              >
                {{ t("settings.smb-view-password") }}
              </RBtn>
            </template>
          </RTooltip>
          <RTooltip :text="t('common.delete')" location="top">
            <template #activator="{ props: tooltipProps }">
              <RBtn
                v-bind="tooltipProps"
                icon="mdi-delete-outline"
                variant="text"
                color="danger"
                size="small"
                :aria-label="t('common.delete')"
                @click="deleteUser(row as SmbUserSchema)"
              />
            </template>
          </RTooltip>
        </div>
      </template>
    </RTable>

    <RDialog
      v-model="showForm"
      icon="mdi-account-network-outline"
      :width="920"
      scroll-content
    >
      <template #header>
        {{
          editingUser ? t("settings.smb-edit-user") : t("settings.smb-new-user")
        }}
      </template>
      <template #content>
        <RForm ref="formRef" class="r-v2-smb__form" @submit="saveUser">
          <RTextField
            v-model="username"
            prefix-label="stacked"
            :disabled="Boolean(editingUser)"
            :rules="[
              (value: string) =>
                Boolean(value) || t('settings.smb-username-required'),
              (value: string) =>
                /^[a-z][a-z0-9._-]{2,31}$/.test(value) ||
                t('settings.smb-username-invalid'),
            ]"
          >
            <template #prefix-label>
              <RIcon icon="mdi-account-outline" size="14" />
              {{ t("settings.smb-username") }}
            </template>
          </RTextField>

          <div class="r-v2-smb__platform-heading">
            <div>
              <strong>{{ t("settings.smb-platform-access") }}</strong>
              <span>{{ t("settings.smb-platform-access-hint") }}</span>
            </div>
            <RTag
              tone="info"
              :text="
                t('settings.smb-platforms-selected', {
                  selected: selectedPlatformCount,
                  total: sortedPlatforms.length,
                })
              "
              size="small"
            />
          </div>
          <div class="r-v2-smb__bulk">
            <strong>{{ t("settings.smb-bulk-actions") }}</strong>
            <div class="r-v2-smb__bulk-actions">
              <RBtn
                variant="outlined"
                color="info"
                size="small"
                prepend-icon="mdi-eye-outline"
                @click="setAllPlatformAccess('read')"
              >
                {{ t("settings.smb-all-read") }}
              </RBtn>
              <RBtn
                variant="outlined"
                color="warning"
                size="small"
                prepend-icon="mdi-pencil-outline"
                @click="setAllPlatformAccess('write')"
              >
                {{ t("settings.smb-all-write") }}
              </RBtn>
              <RBtn
                variant="text"
                size="small"
                prepend-icon="mdi-close-circle-outline"
                @click="setAllPlatformAccess()"
              >
                {{ t("common.clear") }}
              </RBtn>
            </div>
          </div>
          <RTextField
            v-model="platformSearch"
            :label="t('settings.search-platforms')"
            prepend-inner-icon="mdi-magnify"
            clearable
            hide-details
          />
          <div class="r-v2-smb__platforms">
            <div
              v-for="platform in filteredPlatforms"
              :key="platform.id"
              class="r-v2-smb__platform-card"
            >
              <div class="r-v2-smb__platform-name">
                <RIcon icon="mdi-gamepad-variant-outline" size="18" />
                <strong>{{ platform.display_name }}</strong>
              </div>
              <div
                class="r-v2-smb__access-options"
                role="radiogroup"
                :aria-label="platform.display_name"
              >
                <RBtn
                  :variant="
                    !accessByPlatform[platform.id] ? 'flat' : 'outlined'
                  "
                  :class="{
                    'r-v2-smb__access-option--active':
                      !accessByPlatform[platform.id],
                  }"
                  size="small"
                  :prepend-icon="
                    !accessByPlatform[platform.id]
                      ? 'mdi-check-bold'
                      : undefined
                  "
                  :aria-pressed="!accessByPlatform[platform.id]"
                  @click="setPlatformAccess(platform.id, 'none')"
                >
                  {{ t("settings.smb-none") }}
                </RBtn>
                <RBtn
                  :variant="
                    accessByPlatform[platform.id] === 'read'
                      ? 'flat'
                      : 'outlined'
                  "
                  color="info"
                  size="small"
                  :class="{
                    'r-v2-smb__access-option--active':
                      accessByPlatform[platform.id] === 'read',
                  }"
                  :prepend-icon="
                    accessByPlatform[platform.id] === 'read'
                      ? 'mdi-check-bold'
                      : 'mdi-eye-outline'
                  "
                  :aria-pressed="accessByPlatform[platform.id] === 'read'"
                  @click="setPlatformAccess(platform.id, 'read')"
                >
                  {{ t("settings.smb-read") }}
                </RBtn>
                <RBtn
                  :variant="
                    accessByPlatform[platform.id] === 'write'
                      ? 'flat'
                      : 'outlined'
                  "
                  color="warning"
                  size="small"
                  :class="{
                    'r-v2-smb__access-option--active':
                      accessByPlatform[platform.id] === 'write',
                  }"
                  :prepend-icon="
                    accessByPlatform[platform.id] === 'write'
                      ? 'mdi-check-bold'
                      : 'mdi-pencil-outline'
                  "
                  :aria-pressed="accessByPlatform[platform.id] === 'write'"
                  @click="setPlatformAccess(platform.id, 'write')"
                >
                  {{ t("settings.smb-write") }}
                </RBtn>
              </div>
            </div>
          </div>
          <p
            v-if="filteredPlatforms.length === 0"
            class="r-v2-smb__empty-platforms"
          >
            <RIcon icon="mdi-magnify-close" size="20" />
            {{ t("settings.smb-no-platforms-found") }}
          </p>
        </RForm>
      </template>
      <template #footer>
        <RBtn variant="text" @click="showForm = false">
          {{ t("common.cancel") }}
        </RBtn>
        <div class="r-v2-smb__spacer" />
        <RBtn variant="flat" :loading="submitting" @click="saveUser">
          {{ editingUser ? t("common.apply") : t("settings.smb-create") }}
        </RBtn>
      </template>
    </RDialog>

    <RDialog v-model="showCredential" icon="mdi-key-variant" :width="620">
      <template #header>{{ t("settings.smb-credential-title") }}</template>
      <template #content>
        <div v-if="credential" class="r-v2-smb__credential">
          <p class="r-v2-smb__warning">
            <RIcon icon="mdi-alert-outline" size="17" />
            {{ t("settings.smb-credential-warning") }}
          </p>
          <RTextField
            :model-value="credential.username"
            readonly
            prefix-label="stacked"
          >
            <template #prefix-label>{{ t("settings.smb-username") }}</template>
          </RTextField>
          <RTextField
            :model-value="credential.password"
            :type="credentialVisible ? 'text' : 'password'"
            readonly
            prefix-label="stacked"
          >
            <template #prefix-label>{{ t("settings.smb-password") }}</template>
          </RTextField>
          <RBtn
            variant="outlined"
            :prepend-icon="
              credentialVisible ? 'mdi-eye-off-outline' : 'mdi-eye-outline'
            "
            @click="credentialVisible = !credentialVisible"
          >
            {{
              credentialVisible
                ? t("settings.smb-hide-password")
                : t("settings.smb-reveal-password")
            }}
          </RBtn>
          <RBtn
            variant="flat"
            prepend-icon="mdi-content-copy"
            @click="copyPassword"
          >
            {{ t("settings.smb-copy-password") }}
          </RBtn>
          <div class="r-v2-smb__shares">
            <strong>{{ t("settings.smb-shares") }}</strong>
            <code
              v-for="permission in credential.permissions"
              :key="permission.platform_id"
              >{{ permission.share_name }}</code
            >
          </div>
        </div>
      </template>
      <template #footer>
        <div class="r-v2-smb__spacer" />
        <RBtn variant="flat" @click="closeCredential">
          {{ t("common.close") }}
        </RBtn>
      </template>
    </RDialog>

    <RDialog
      v-model="showLogs"
      icon="mdi-text-box-search-outline"
      :width="980"
      scroll-content
    >
      <template #header>{{ t("settings.smb-logs-title") }}</template>
      <template #content>
        <div class="r-v2-smb__logs-toolbar">
          <span>{{ t("settings.smb-logs-hint") }}</span>
          <RBtn
            variant="text"
            size="small"
            prepend-icon="mdi-refresh"
            :loading="logsLoading"
            @click="refreshLogs"
          >
            {{ t("settings.smb-refresh") }}
          </RBtn>
        </div>
        <pre class="r-v2-smb__logs">{{
          logLines.length ? logLines.join("\n") : t("settings.smb-logs-empty")
        }}</pre>
      </template>
      <template #footer>
        <div class="r-v2-smb__spacer" />
        <RBtn variant="flat" @click="showLogs = false">
          {{ t("common.close") }}
        </RBtn>
      </template>
    </RDialog>
  </div>
</template>

<style scoped>
.r-v2-smb {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.r-v2-smb__header,
.r-v2-smb__title-row,
.r-v2-smb__header-actions,
.r-v2-smb__actions,
.r-v2-smb__permissions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.r-v2-smb__header {
  justify-content: space-between;
  flex-wrap: wrap;
}
.r-v2-smb__header h3,
.r-v2-smb__header p {
  margin: 0;
}
.r-v2-smb__header p,
.r-v2-smb__platform-heading span {
  color: var(--r-color-text-secondary);
}
.r-v2-smb__permissions {
  flex-wrap: wrap;
}
.r-v2-smb__form,
.r-v2-smb__credential,
.r-v2-smb__shares {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.r-v2-smb__server-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
.r-v2-smb__server-heading,
.r-v2-smb__logs-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.r-v2-smb__server-heading > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.r-v2-smb__server-heading span,
.r-v2-smb__server-grid span,
.r-v2-smb__server-grid small,
.r-v2-smb__logs-toolbar span {
  color: var(--r-color-text-secondary);
}
.r-v2-smb__server-grid {
  display: grid;
  grid-template-columns: minmax(220px, 2fr) repeat(4, minmax(120px, 1fr));
  gap: 10px;
}
.r-v2-smb__server-grid > div {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
  padding: 12px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface-2);
}
.r-v2-smb__server-grid code,
.r-v2-smb__server-grid strong,
.r-v2-smb__server-grid small {
  overflow-wrap: anywhere;
}
.r-v2-smb__service-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  color: var(--r-color-text-secondary);
}
.r-v2-smb__logs {
  min-height: 320px;
  max-height: 58vh;
  margin: 0;
  padding: 14px;
  overflow: auto;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-surface-2);
  color: var(--r-color-text-primary);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
@media (max-width: 1100px) {
  .r-v2-smb__server-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 640px) {
  .r-v2-smb__server-grid {
    grid-template-columns: 1fr;
  }
}
.r-v2-smb__platform-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.r-v2-smb__platform-heading > div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.r-v2-smb__bulk {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
.r-v2-smb__bulk-actions,
.r-v2-smb__access-options {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.r-v2-smb__platforms {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 10px;
}
.r-v2-smb__platform-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
}
.r-v2-smb__platform-name {
  display: flex;
  align-items: center;
  gap: 8px;
}
.r-v2-smb__access-options > * {
  flex: 1 1 auto;
}
.r-v2-smb__access-option--active {
  box-shadow: inset 0 0 0 2px currentColor;
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-smb__empty-platforms {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 88px;
  margin: 0;
  color: var(--r-color-text-secondary);
}
.r-v2-smb__warning {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--r-color-warning) 35%, transparent);
  border-radius: var(--r-radius-md);
  color: var(--r-color-warning);
}
.r-v2-smb__spacer {
  flex: 1;
}
.r-v2-smb__shares code {
  padding: 8px 10px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-surface-2);
}
</style>
