<script setup lang="ts">
import {
  RBtn,
  RCheckbox,
  RDialog,
  REmptyState,
  RIcon,
  RSpinner,
} from "@v2/lib";
import type { Emitter } from "mitt";
import { computed, inject, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  DeviceSchema,
  InstallRequestSchema,
  InstallStatus,
} from "@/__generated__";
import deviceApi from "@/services/api/device";
import deviceInstallApi from "@/services/api/device-install";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import { errorMessage } from "@/v2/utils/errorMessage";

defineOptions({ inheritAttrs: false });

const SEND_DELAY_MS = 3000;
const ACTIVE_STATUSES: InstallStatus[] = ["pending", "taken"];
const DELIVERED_STATUSES: InstallStatus[] = ["done", "already_installed"];
const STATUS_LABEL_KEYS: Record<InstallStatus, string> = {
  pending: "rom.install-on-device-status-pending",
  taken: "rom.install-on-device-status-taken",
  done: "rom.install-on-device-status-done",
  already_installed: "rom.install-on-device-status-already-installed",
  failed: "rom.install-on-device-status-failed",
  cancelled: "rom.install-on-device-status-cancelled",
};

const { t } = useI18n();
const { mdAndUp } = useBreakpoint();
const snackbar = useSnackbar();
const emitter = inject<Emitter<Events>>("emitter");
const alive = useIsAlive();

const show = ref(false);
const rom = ref<SimpleRom | null>(null);
const loading = ref(false);
const loadError = ref<string | null>(null);
const devices = ref<DeviceSchema[]>([]);
const onlineIds = ref(new Set<string>());
const requests = ref(new Map<string, InstallRequestSchema>());
const preparing = ref(new Set<string>());
const busy = ref(new Set<string>());
const timers = new Map<string, ReturnType<typeof setTimeout>>();

function lastSeenTime(device: DeviceSchema): number {
  return device.last_seen ? Date.parse(device.last_seen) : 0;
}

const installableDevices = computed(() =>
  devices.value
    .filter((device) => device.capabilities?.remote_install === true)
    .sort((a, b) => lastSeenTime(b) - lastSeenTime(a)),
);

function applyRequest(request: InstallRequestSchema) {
  const current = requests.value.get(request.device_id);
  if (current && current.created_at > request.created_at) return;
  if (current?.id === request.id && current.updated_at > request.updated_at) {
    return;
  }
  requests.value.set(request.device_id, request);
}

function stopPreparing(deviceId: string) {
  const timer = timers.get(deviceId);
  if (timer !== undefined) clearTimeout(timer);
  timers.delete(deviceId);
  preparing.value.delete(deviceId);
}

function sendPendingNow() {
  const target = rom.value;
  for (const deviceId of [...timers.keys()]) {
    stopPreparing(deviceId);
    if (target) void send(deviceId, target);
  }
}

async function load(target: SimpleRom) {
  loading.value = true;
  loadError.value = null;
  try {
    const [devicesResponse, onlineResponse, installsResponse] =
      await Promise.all([
        deviceApi.fetchDevices(),
        deviceApi.fetchOnlineDeviceIds(),
        deviceInstallApi.fetchRomInstalls(target.id),
      ]);
    if (!alive.value || rom.value?.id !== target.id) return;
    devices.value = devicesResponse.data;
    onlineIds.value = new Set(onlineResponse.data);
    installsResponse.data.forEach(applyRequest);
  } catch (error) {
    if (alive.value && rom.value?.id === target.id) {
      loadError.value = errorMessage(error);
    }
  } finally {
    if (alive.value && rom.value?.id === target.id) loading.value = false;
  }
}

function retry() {
  if (rom.value) void load(rom.value);
}

const openHandler = (target: SimpleRom) => {
  sendPendingNow();
  rom.value = target;
  devices.value = [];
  onlineIds.value = new Set();
  requests.value = new Map();
  busy.value = new Set();
  show.value = true;
  void load(target);
};
emitter?.on("showInstallOnDeviceDialog", openHandler);
onBeforeUnmount(() => {
  emitter?.off("showInstallOnDeviceDialog", openHandler);
  sendPendingNow();
});

watch(show, (open) => {
  if (!open) sendPendingNow();
});

useSocketEvent<InstallRequestSchema>("install:updated", (request) => {
  if (rom.value?.id === request.rom_id) applyRequest(request);
});

async function send(deviceId: string, target: SimpleRom) {
  const inFlight = busy.value;
  inFlight.add(deviceId);
  try {
    const { data } = await deviceInstallApi.createInstall(deviceId, {
      rom_id: target.id,
    });
    if (alive.value && rom.value?.id === target.id) applyRequest(data);
  } catch (error) {
    if (!alive.value) return;
    snackbar.error(
      t("rom.install-on-device-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    inFlight.delete(deviceId);
  }
}

function startPreparing(deviceId: string) {
  stopPreparing(deviceId);
  preparing.value.add(deviceId);
  timers.set(
    deviceId,
    setTimeout(() => {
      stopPreparing(deviceId);
      if (rom.value) void send(deviceId, rom.value);
    }, SEND_DELAY_MS),
  );
}

async function cancel(request: InstallRequestSchema) {
  const inFlight = busy.value;
  inFlight.add(request.device_id);
  try {
    const { data } = await deviceInstallApi.cancelInstall(
      request.device_id,
      request.id,
    );
    if (alive.value && rom.value?.id === data.rom_id) applyRequest(data);
  } catch (error) {
    if (!alive.value) return;
    snackbar.error(
      t("rom.install-on-device-cancel-failed", { error: errorMessage(error) }),
      { icon: "mdi-close-circle" },
    );
  } finally {
    inFlight.delete(request.device_id);
  }
}

function isActive(
  request: InstallRequestSchema | undefined,
): request is InstallRequestSchema {
  return request !== undefined && ACTIVE_STATUSES.includes(request.status);
}

function settledStatus(device: DeviceSchema): InstallStatus | undefined {
  if (preparing.value.has(device.id)) return undefined;
  return requests.value.get(device.id)?.status;
}

function isDelivered(device: DeviceSchema): boolean {
  const status = settledStatus(device);
  return status !== undefined && DELIVERED_STATUSES.includes(status);
}

function isChecked(device: DeviceSchema): boolean {
  return (
    preparing.value.has(device.id) ||
    isActive(requests.value.get(device.id)) ||
    isDelivered(device)
  );
}

function toggle(device: DeviceSchema, checked: boolean) {
  if (isDelivered(device)) return;
  if (checked) {
    startPreparing(device.id);
    return;
  }
  if (preparing.value.has(device.id)) {
    stopPreparing(device.id);
    return;
  }
  const request = requests.value.get(device.id);
  if (isActive(request)) void cancel(request);
}

function isFailed(device: DeviceSchema): boolean {
  return settledStatus(device) === "failed";
}

function subtitleFor(device: DeviceSchema): string | undefined {
  if (preparing.value.has(device.id)) {
    return t("rom.install-on-device-preparing");
  }
  const request = requests.value.get(device.id);
  if (!request) return undefined;
  const label = t(STATUS_LABEL_KEYS[request.status]);
  return request.status === "failed" && request.reason
    ? `${label}: ${request.reason}`
    : label;
}

function deviceName(device: DeviceSchema): string {
  return device.name || device.hostname || device.id;
}

function isOnline(device: DeviceSchema): boolean {
  return onlineIds.value.has(device.id);
}

const announcement = computed(() =>
  installableDevices.value
    .map((device) => {
      const subtitle = subtitleFor(device);
      return subtitle ? `${deviceName(device)}: ${subtitle}` : null;
    })
    .filter((line): line is string => line !== null)
    .join(". "),
);

function closeDialog() {
  sendPendingNow();
  show.value = false;
  rom.value = null;
}
</script>

<template>
  <RDialog
    v-model="show"
    icon="mdi-cellphone-arrow-down"
    :width="mdAndUp ? 440 : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <div class="r-v2-install-device__head">
        <span class="r-v2-install-device__title">
          {{ t("rom.install-on-device") }}
        </span>
        <span v-if="rom" class="r-v2-install-device__subtitle">
          {{ rom.name ?? rom.fs_name }}
        </span>
      </div>
    </template>

    <template #content>
      <div v-if="loading" class="r-v2-install-device__loading">
        <RSpinner />
      </div>
      <REmptyState
        v-else-if="loadError !== null"
        variant="boxed"
        size="small"
        icon="mdi-alert-circle-outline"
        :title="t('rom.install-on-device-load-failed')"
        :hint="loadError"
      >
        <template #actions>
          <RBtn variant="flat" prepend-icon="mdi-refresh" @click="retry">
            {{ t("common.try-again") }}
          </RBtn>
        </template>
      </REmptyState>
      <REmptyState
        v-else-if="installableDevices.length === 0"
        variant="boxed"
        size="small"
        icon="mdi-cellphone-off"
        :hint="t('rom.install-on-device-empty')"
      />
      <ul v-else class="r-v2-install-device__list">
        <li v-for="device in installableDevices" :key="device.id">
          <RCheckbox
            variant="card"
            :model-value="isChecked(device)"
            :disabled="busy.has(device.id) || isDelivered(device)"
            :shape="isDelivered(device) ? 'circle' : undefined"
            :color="isDelivered(device) ? 'success' : undefined"
            :subtitle="subtitleFor(device)"
            @update:model-value="toggle(device, $event)"
          >
            <span class="r-v2-install-device__name">
              <span
                class="r-v2-install-device__presence"
                :class="{
                  'r-v2-install-device__presence--online': isOnline(device),
                }"
                role="img"
                :aria-label="
                  isOnline(device) ? t('common.online') : t('common.offline')
                "
              />
              {{ deviceName(device) }}
            </span>
            <template v-if="isFailed(device)" #subtitle>
              <span class="r-v2-install-device__failed">
                <RIcon icon="mdi-alert-circle" :size="14" />
                {{ subtitleFor(device) }}
              </span>
            </template>
          </RCheckbox>
        </li>
      </ul>
      <p class="r-v2-install-device__live" role="status" aria-live="polite">
        {{ announcement }}
      </p>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-install-device__head {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-1);
  min-width: 0;
}
.r-v2-install-device__title {
  font-size: var(--r-font-size-md);
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-overlay-fg);
}
.r-v2-install-device__subtitle {
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-install-device__loading {
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
}
.r-v2-install-device__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
  max-height: 360px;
  overflow-y: auto;
}
.r-v2-install-device__list :deep(.r-checkbox-wrap) {
  display: flex;
}
.r-v2-install-device__name {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-2);
}
.r-v2-install-device__presence {
  width: var(--r-space-2);
  height: var(--r-space-2);
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--r-color-fg-faint);
}
.r-v2-install-device__presence--online {
  background: var(--r-color-success);
}
.r-v2-install-device__failed {
  display: inline-flex;
  align-items: center;
  gap: var(--r-space-1);
  color: var(--r-color-danger);
}
.r-v2-install-device__live {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
