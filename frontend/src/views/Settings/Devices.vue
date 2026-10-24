<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DeviceSchema, PS3ConsoleCreatePayload } from "@/__generated__";
import PS3ConsoleDialog from "@/components/Settings/PS3ConsoleDialog.vue";
import RenameDeviceDialog from "@/components/Settings/RenameDeviceDialog.vue";
import { useConfirm } from "@/composables/useConfirm";
import { useFetchState } from "@/composables/useFetchState";
import { useSnackbar } from "@/composables/useSnackbar";
import { useSocketEvent } from "@/composables/useSocketEvent";
import { RBtn, RChip, RSwitch, RTable, type RTableColumn } from "@/lib";
import deviceApi from "@/services/api/device";
import storeAuth from "@/stores/auth";
import { formatRelativeDate } from "@/utils";
import { errorMessage } from "@/utils/errorMessage";
import { cachedBrowserDeviceId } from "@/utils/saveSync/browserDevice";

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { user, scopes } = storeToRefs(storeAuth());
const canWrite = computed(() => scopes.value.includes("devices.write"));

const {
  state: devices,
  isLoading: loading,
  execute: refetch,
} = useFetchState(() => deviceApi.fetchDevices().then(({ data }) => data), [], {
  onError: (error) => console.error(error),
});

const thisBrowser = computed(() =>
  user.value ? cachedBrowserDeviceId(user.value.id) : null,
);

// Most recently active first; devices never seen sink to the end.
const sortedDevices = computed(() =>
  [...devices.value].sort((a, b) =>
    (b.last_seen ?? "").localeCompare(a.last_seen ?? ""),
  ),
);

const columns = computed<RTableColumn[]>(() => [
  {
    key: "name",
    label: t("common.name"),
    width: "minmax(0, 2fr)",
    skeletonWidth: 160,
  },
  {
    key: "last_seen",
    label: t("settings.device-last-seen"),
    width: "minmax(0, 1fr)",
    skeletonWidth: 100,
  },
  {
    key: "sync",
    label: t("settings.device-sync"),
    width: "96px",
    skeletonWidth: 36,
  },
  {
    key: "actions",
    label: "",
    width: "136px",
    align: "end",
    skeletonWidth: 0,
  },
]);

function displayName(device: DeviceSchema): string {
  return (
    device.name ||
    device.platform ||
    device.client ||
    t("settings.device-unnamed")
  );
}

function isPS3(device: DeviceSchema): boolean {
  return device.client === "ps3";
}

function detailLine(device: DeviceSchema): string {
  if (isPS3(device)) {
    const minutes = device.sync_config?.poll_interval_minutes;
    return [
      device.platform,
      device.ip_address,
      minutes ? t("settings.ps3-every-minutes", { minutes }) : null,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return [device.platform, device.client, device.client_version]
    .filter(Boolean)
    .join(" · ");
}

function replace(updated: DeviceSchema) {
  devices.value = devices.value.map((d) => (d.id === updated.id ? updated : d));
}

async function toggleSync(device: DeviceSchema, enabled: boolean) {
  replace({ ...device, sync_enabled: enabled });
  try {
    const { data } = await deviceApi.updateDevice(device.id, {
      sync_enabled: enabled,
    });
    replace(data);
  } catch (error) {
    replace(device);
    snackbar.error(
      t("settings.device-update-failed", { detail: errorMessage(error) }),
    );
  }
}

const renaming = ref<DeviceSchema | null>(null);
const renameOpen = ref(false);
const renameBusy = ref(false);

function openRename(device: DeviceSchema) {
  renaming.value = device;
  renameOpen.value = true;
}

async function rename(name: string) {
  const device = renaming.value;
  if (!device) return;
  renameBusy.value = true;
  try {
    const { data } = await deviceApi.updateDevice(device.id, { name });
    replace(data);
    renameOpen.value = false;
  } catch (error) {
    snackbar.error(
      t("settings.device-update-failed", { detail: errorMessage(error) }),
    );
  } finally {
    renameBusy.value = false;
  }
}

const consoleEditing = ref<DeviceSchema | null>(null);
const consoleOpen = ref(false);
const consoleBusy = ref(false);

function openConsole(device: DeviceSchema | null) {
  consoleEditing.value = device;
  consoleOpen.value = true;
}

async function saveConsole(payload: PS3ConsoleCreatePayload) {
  const editing = consoleEditing.value;
  consoleBusy.value = true;
  try {
    if (editing) {
      const { data } = await deviceApi.updatePS3(editing.id, payload);
      replace(data);
    } else {
      const { data } = await deviceApi.addPS3(payload);
      devices.value = [...devices.value, data];
      snackbar.success(t("settings.ps3-added"), { icon: "mdi-check-bold" });
    }
    consoleOpen.value = false;
  } catch (error) {
    snackbar.error(
      t("settings.ps3-save-failed", { detail: errorMessage(error) }),
    );
  } finally {
    consoleBusy.value = false;
  }
}

const syncing = ref(new Set<string>());

async function syncNow(device: DeviceSchema) {
  syncing.value = new Set(syncing.value).add(device.id);
  try {
    await deviceApi.syncPS3(device.id);
    snackbar.success(t("settings.ps3-sync-queued"), { icon: "mdi-sync" });
  } catch (error) {
    snackbar.error(
      t("settings.ps3-sync-failed", { detail: errorMessage(error) }),
    );
  } finally {
    const next = new Set(syncing.value);
    next.delete(device.id);
    syncing.value = next;
  }
}

/** The backend's `sync:completed` / `sync:error` payloads, which have no generated type. */
interface SyncFinishedPayload {
  device_id: string;
  error?: string;
}

function isListedPS3(deviceId: string): DeviceSchema | undefined {
  return devices.value.find((d) => d.id === deviceId && isPS3(d));
}

// A console sync runs in a worker, so its outcome only arrives over the socket.
useSocketEvent<SyncFinishedPayload>("sync:completed", (payload) => {
  if (isListedPS3(payload.device_id)) void refetch();
});
useSocketEvent<SyncFinishedPayload>("sync:error", (payload) => {
  const device = isListedPS3(payload.device_id);
  if (!device) return;
  snackbar.error(
    t("settings.ps3-sync-error", {
      name: displayName(device),
      detail: payload.error ?? "",
    }),
  );
});

async function remove(device: DeviceSchema) {
  const ok = await confirm({
    title: t("common.confirm-deletion"),
    body: t("settings.device-confirm-delete", { name: displayName(device) }),
    confirmText: t("common.delete"),
    tone: "danger",
  });
  if (!ok) return;
  try {
    await deviceApi.deleteDevice(device.id);
    devices.value = devices.value.filter((d) => d.id !== device.id);
    snackbar.success(t("settings.device-deleted"), { icon: "mdi-check-bold" });
  } catch (error) {
    snackbar.error(
      t("settings.device-delete-failed", { detail: errorMessage(error) }),
    );
  }
}
</script>

<template>
  <div class="r-section-stack">
    <div class="r-devices__header">
      <p class="r-devices__intro">{{ t("settings.devices-description") }}</p>
      <RBtn
        v-if="canWrite"
        variant="translucent"
        size="small"
        prepend-icon="mdi-sony-playstation"
        @click="openConsole(null)"
      >
        {{ t("settings.ps3-add") }}
      </RBtn>
    </div>

    <RTable
      :columns="columns"
      :items="sortedDevices"
      :item-key="(r) => (r as DeviceSchema).id"
      :loading="loading"
      empty-icon="mdi-devices"
      :empty-message="t('settings.devices-empty')"
    >
      <template #cell.name="{ row }">
        <div class="r-devices__name-cell">
          <div class="r-devices__name-line">
            <span class="r-devices__name">
              {{ displayName(row as DeviceSchema) }}
            </span>
            <RChip
              v-if="(row as DeviceSchema).id === thisBrowser"
              size="x-small"
              color="primary"
              variant="outlined"
            >
              {{ t("settings.device-this-browser") }}
            </RChip>
          </div>
          <span v-if="detailLine(row as DeviceSchema)" class="r-devices__meta">
            {{ detailLine(row as DeviceSchema) }}
          </span>
        </div>
      </template>
      <template #cell.last_seen="{ row }">
        <span class="r-devices__meta">
          {{
            (row as DeviceSchema).last_seen
              ? formatRelativeDate((row as DeviceSchema).last_seen!)
              : "—"
          }}
        </span>
      </template>
      <template #cell.sync="{ row }">
        <RSwitch
          :model-value="(row as DeviceSchema).sync_enabled"
          :disabled="!canWrite"
          :aria-label="t('settings.device-sync')"
          @update:model-value="(v) => toggleSync(row as DeviceSchema, v)"
        />
      </template>
      <template #cell.actions="{ row }">
        <div v-if="canWrite" class="r-devices__actions">
          <template v-if="isPS3(row as DeviceSchema)">
            <RBtn
              variant="text"
              size="small"
              icon="mdi-sync"
              :loading="syncing.has((row as DeviceSchema).id)"
              :disabled="!(row as DeviceSchema).sync_enabled"
              :aria-label="t('settings.ps3-sync-now')"
              :title="t('settings.ps3-sync-now')"
              @click="syncNow(row as DeviceSchema)"
            />
            <RBtn
              variant="text"
              size="small"
              icon="mdi-cog-outline"
              :aria-label="t('settings.ps3-edit')"
              :title="t('settings.ps3-edit')"
              @click="openConsole(row as DeviceSchema)"
            />
          </template>
          <RBtn
            v-else
            variant="text"
            size="small"
            icon="mdi-pencil-outline"
            :aria-label="t('settings.device-rename')"
            :title="t('settings.device-rename')"
            @click="openRename(row as DeviceSchema)"
          />
          <RBtn
            variant="text"
            size="small"
            icon="mdi-trash-can-outline"
            color="danger"
            :aria-label="t('common.delete')"
            :title="t('common.delete')"
            class="r-devices__delete"
            @click="remove(row as DeviceSchema)"
          />
        </div>
      </template>
    </RTable>

    <RenameDeviceDialog
      v-model="renameOpen"
      :name="renaming ? displayName(renaming) : ''"
      :busy="renameBusy"
      @submit="rename"
    />

    <PS3ConsoleDialog
      v-model="consoleOpen"
      :device="consoleEditing"
      :busy="consoleBusy"
      @submit="saveConsole"
    />
  </div>
</template>

<style scoped>
.r-devices__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
  flex-wrap: wrap;
}

.r-devices__intro {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-devices__name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.r-devices__name-line {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  min-width: 0;
}

.r-devices__name {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-devices__meta {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-devices__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.r-devices__delete {
  --r-btn-color: color-mix(in srgb, var(--r-color-danger) 70%, transparent);
}
.r-devices__delete:hover {
  --r-btn-color: var(--r-color-danger);
}
</style>
