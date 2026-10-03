<script setup lang="ts">
import { RBtn, RChip, RSwitch, RTable, type RTableColumn } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { DeviceSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import storeAuth from "@/stores/auth";
import { formatRelativeDate } from "@/utils";
import RenameDeviceDialog from "@/v2/components/Settings/RenameDeviceDialog.vue";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useFetchState } from "@/v2/composables/useFetchState";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { errorMessage } from "@/v2/utils/errorMessage";
import {
  cachedBrowserDeviceId,
  forgetBrowserDeviceId,
} from "@/v2/utils/saveSync/browserDevice";

const { t } = useI18n();
const snackbar = useSnackbar();
const confirm = useConfirm();
const { user, scopes } = storeToRefs(storeAuth());
const canWrite = computed(() => scopes.value.includes("devices.write"));

const { state: devices, isLoading: loading } = useFetchState(
  () => deviceApi.fetchDevices().then(({ data }) => data),
  [],
  { onError: (error) => console.error(error) },
);

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
    width: "96px",
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

function detailLine(device: DeviceSchema): string {
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
    // EmulatorJS sends the cached id unchecked, and a removed one 404s.
    if (user.value && device.id === thisBrowser.value) {
      forgetBrowserDeviceId(user.value.id);
    }
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
  <div class="r-v2-section-stack">
    <p class="r-v2-devices__intro">{{ t("settings.devices-description") }}</p>

    <RTable
      :columns="columns"
      :items="sortedDevices"
      :item-key="(r) => (r as DeviceSchema).id"
      :loading="loading"
      empty-icon="mdi-devices"
      :empty-message="t('settings.devices-empty')"
    >
      <template #cell.name="{ row }">
        <div class="r-v2-devices__name-cell">
          <div class="r-v2-devices__name-line">
            <span class="r-v2-devices__name">
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
          <span
            v-if="detailLine(row as DeviceSchema)"
            class="r-v2-devices__meta"
          >
            {{ detailLine(row as DeviceSchema) }}
          </span>
        </div>
      </template>
      <template #cell.last_seen="{ row }">
        <span class="r-v2-devices__meta">
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
        <div v-if="canWrite" class="r-v2-devices__actions">
          <RBtn
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
            class="r-v2-devices__delete"
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
  </div>
</template>

<style scoped>
.r-v2-devices__intro {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-devices__name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.r-v2-devices__name-line {
  display: flex;
  align-items: center;
  gap: var(--r-space-2);
  min-width: 0;
}

.r-v2-devices__name {
  font-weight: var(--r-font-weight-semibold);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-devices__meta {
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-devices__actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.r-v2-devices__delete {
  --r-btn-color: color-mix(in srgb, var(--r-color-danger) 70%, transparent);
}
.r-v2-devices__delete:hover {
  --r-btn-color: var(--r-color-danger);
}
</style>
