// Launcher shortcuts: which games the user has queued for Steam on each paired
// desktop companion, plus the companions themselves. One store-wide fetch
// serves every GameActionBtn in a gallery, so per-card surfaces read state
// with no request of their own; `shortcuts:changed` keeps it current.
import { defineStore } from "pinia";
import { computed, effectScope, ref } from "vue";
import type { DeviceSchema, ShortcutSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import shortcutApi from "@/services/api/shortcut";
import storeAuth from "@/stores/auth";
import type { SocketEventHandle } from "@/v2/composables/useSocketEvent";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";

/** Device `client` a desktop companion registers with (KNOWN_DEVICES). */
export const STEAM_COMPANION_CLIENT = "steam-companion";

export function launcherDeviceName(device: DeviceSchema): string {
  return device.name ?? device.hostname ?? device.id;
}

const REFRESH_DEBOUNCE_MS = 300;

export const useShortcutsStore = defineStore("shortcuts", () => {
  const auth = storeAuth();

  const devices = ref<DeviceSchema[]>([]);
  const shortcuts = ref<ShortcutSchema[]>([]);
  const loaded = ref(false);
  let inflight: Promise<void> | null = null;
  let refreshTimer: ReturnType<typeof setTimeout> | null = null;
  // The subscription belongs to the store, not to whichever component happened
  // to trigger the first load: cleanup runs on the scope that was active when
  // useSocketEvent was called, so a component scope would take the listener
  // down with it on unmount.
  const socketScope = effectScope(true);
  let socketHandle: SocketEventHandle | null = null;

  // Reading devices and shortcuts needs both scopes; a viewer without them
  // simply never sees the Steam actions rather than tripping a 403.
  const canRead = computed(
    () =>
      auth.scopes.includes("devices.read") &&
      auth.scopes.includes("roms.user.read"),
  );

  const launcherDevices = computed(() =>
    devices.value.filter((d) => d.client === STEAM_COMPANION_CLIENT),
  );
  const hasLauncherDevices = computed(() => launcherDevices.value.length > 0);

  const byRom = computed(() => {
    const map = new Map<number, ShortcutSchema[]>();
    for (const s of shortcuts.value) {
      const list = map.get(s.rom_id);
      if (list) list.push(s);
      else map.set(s.rom_id, [s]);
    }
    return map;
  });

  function shortcutsForRom(romId: number): ShortcutSchema[] {
    return byRom.value.get(romId) ?? [];
  }

  function shortcutsForDevice(deviceId: string): ShortcutSchema[] {
    return shortcuts.value.filter((s) => s.device_id === deviceId);
  }

  /** Whether a device reported a way to play the platform. Null means the
   *  device has not reported yet, which the UI treats as unknown, not no. */
  function deviceSupports(
    device: DeviceSchema,
    platformSlug: string | null | undefined,
  ): boolean | null {
    if (!device.launch_capabilities) return null;
    if (!platformSlug) return false;
    return Boolean(device.launch_capabilities[platformSlug]);
  }

  async function fetch(): Promise<void> {
    if (!canRead.value) return;
    if (inflight) return inflight;
    inflight = (async () => {
      try {
        const [deviceRes, shortcutRes] = await Promise.all([
          deviceApi.fetchDevices(),
          shortcutApi.fetchShortcuts(),
        ]);
        devices.value = deviceRes.data;
        shortcuts.value = shortcutRes.data;
        loaded.value = true;
      } catch (error) {
        console.error("Failed to load launcher shortcuts", error);
      } finally {
        inflight = null;
      }
    })();
    return inflight;
  }

  /** First-call load; later calls are free. Also arms the socket refresh. */
  async function ensureLoaded(): Promise<void> {
    if (!socketHandle && canRead.value) {
      socketHandle = socketScope.run(() =>
        useSocketEvent("shortcuts:changed", scheduleRefresh),
      ) as SocketEventHandle;
    }
    if (loaded.value) return;
    await fetch();
  }

  // Several acks can land in quick succession while a companion works through
  // its queue; one refetch shortly after the last is enough.
  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      void fetch();
    }, REFRESH_DEBOUNCE_MS);
  }

  function upsertLocal(row: ShortcutSchema) {
    const idx = shortcuts.value.findIndex((s) => s.id === row.id);
    if (idx === -1) shortcuts.value.push(row);
    else shortcuts.value.splice(idx, 1, row);
  }

  async function add(romId: number, deviceId: string): Promise<ShortcutSchema> {
    const { data } = await shortcutApi.addShortcut({ romId, deviceId });
    upsertLocal(data);
    return data;
  }

  /** Removes or queues a removal. The server deletes a row that never reached
   *  the device and returns it as-is; otherwise it comes back `pending_remove`. */
  async function remove(shortcut: ShortcutSchema): Promise<ShortcutSchema> {
    const { data } = await shortcutApi.removeShortcut(shortcut.id);
    if (data.status === "pending_remove") upsertLocal(data);
    else shortcuts.value = shortcuts.value.filter((s) => s.id !== data.id);
    return data;
  }

  /** Logout clears every store that offers this, so the next account starts
   *  from nothing rather than seeing the previous one's launchers. */
  function reset() {
    devices.value = [];
    shortcuts.value = [];
    loaded.value = false;
    inflight = null;
    if (refreshTimer) {
      clearTimeout(refreshTimer);
      refreshTimer = null;
    }
    socketHandle?.stop();
    socketHandle = null;
  }

  return {
    devices,
    shortcuts,
    loaded,
    canRead,
    launcherDevices,
    hasLauncherDevices,
    shortcutsForRom,
    shortcutsForDevice,
    deviceSupports,
    fetch,
    ensureLoaded,
    add,
    remove,
    reset,
  };
});
