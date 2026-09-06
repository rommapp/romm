import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import type { DeviceSchema, ShortcutSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import shortcutApi from "@/services/api/shortcut";
import { useShortcutsStore } from "@/stores/shortcuts";

const scopes: string[] = ["devices.read", "roms.user.read"];
let socketHandler: ((payload: unknown) => void) | null = null;

vi.mock("@/services/api/device", () => ({
  default: { fetchDevices: vi.fn() },
}));
vi.mock("@/services/api/shortcut", () => ({
  default: {
    fetchShortcuts: vi.fn(),
    addShortcut: vi.fn(),
    removeShortcut: vi.fn(),
  },
}));
vi.mock("@/stores/auth", () => ({
  default: () => ({ scopes }),
}));
vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: (_event: string, handler: (payload: unknown) => void) => {
    socketHandler = handler;
    return { stop: vi.fn() };
  },
}));

const fetchDevices = deviceApi.fetchDevices as unknown as Mock;
const fetchShortcuts = shortcutApi.fetchShortcuts as unknown as Mock;
const addShortcut = shortcutApi.addShortcut as unknown as Mock;
const removeShortcut = shortcutApi.removeShortcut as unknown as Mock;

function device(
  id: string,
  client: string,
  caps: Record<string, string | null> | null = null,
): DeviceSchema {
  return {
    id,
    user_id: 1,
    name: id,
    platform: "linux",
    client,
    client_version: "1",
    ip_address: null,
    mac_address: null,
    hostname: null,
    client_device_identifier: null,
    sync_mode: "api",
    sync_enabled: true,
    sync_config: null,
    launch_capabilities: caps,
    last_seen: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function shortcut(
  id: number,
  romId: number,
  deviceId: string,
  status: ShortcutSchema["status"],
): ShortcutSchema {
  return {
    id,
    user_id: 1,
    device_id: deviceId,
    rom_id: romId,
    status,
    launch_mode: null,
    steam_app_id: null,
    error: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("shortcuts store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    socketHandler = null;
    scopes.splice(0, scopes.length, "devices.read", "roms.user.read");
    fetchDevices.mockReset().mockResolvedValue({
      data: [
        device("desktop", "steam-companion", {
          snes: "retroarch:snes9x",
          switch: null,
        }),
        device("phone", "argosy-launcher"),
      ],
    });
    fetchShortcuts
      .mockReset()
      .mockResolvedValue({ data: [shortcut(1, 7, "desktop", "added")] });
    addShortcut.mockReset();
    removeShortcut.mockReset();
  });

  it("collapses concurrent loads into one request pair and keeps only launcher devices", async () => {
    const store = useShortcutsStore();
    await Promise.all([
      store.ensureLoaded(),
      store.ensureLoaded(),
      store.ensureLoaded(),
    ]);
    expect(fetchDevices).toHaveBeenCalledTimes(1);
    expect(fetchShortcuts).toHaveBeenCalledTimes(1);
    expect(store.launcherDevices.map((d) => d.id)).toEqual(["desktop"]);
    expect(store.shortcutsForRom(7)).toHaveLength(1);
    expect(store.shortcutsForRom(8)).toEqual([]);
  });

  it("does not fetch without the read scopes", async () => {
    scopes.splice(0, scopes.length, "roms.read");
    const store = useShortcutsStore();
    await store.ensureLoaded();
    expect(fetchDevices).not.toHaveBeenCalled();
    expect(store.hasLauncherDevices).toBe(false);
  });

  it("reads capability as yes, no, or unknown", async () => {
    const store = useShortcutsStore();
    await store.ensureLoaded();
    const desktop = store.launcherDevices[0]!;
    expect(store.deviceSupports(desktop, "snes")).toBe(true);
    expect(store.deviceSupports(desktop, "switch")).toBe(false);
    expect(store.deviceSupports(desktop, "n64")).toBe(false);
    expect(
      store.deviceSupports(device("fresh", "steam-companion"), "snes"),
    ).toBeNull();
  });

  it("refetches once after a burst of shortcuts:changed events", async () => {
    vi.useFakeTimers();
    try {
      const store = useShortcutsStore();
      await store.ensureLoaded();
      expect(socketHandler).not.toBeNull();
      socketHandler?.({ device_id: "desktop" });
      socketHandler?.({ device_id: "desktop" });
      socketHandler?.({ device_id: "desktop" });
      await vi.runAllTimersAsync();
      expect(fetchShortcuts).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("add upserts the returned row and remove drops or updates it", async () => {
    const store = useShortcutsStore();
    await store.ensureLoaded();

    addShortcut.mockResolvedValue({
      data: shortcut(2, 8, "desktop", "pending_add"),
    });
    await store.add(8, "desktop");
    expect(store.shortcutsForRom(8)[0]?.status).toBe("pending_add");

    // Re-adding a failed row comes back as the same id, so it replaces.
    addShortcut.mockResolvedValue({
      data: shortcut(2, 8, "desktop", "pending_add"),
    });
    await store.add(8, "desktop");
    expect(store.shortcutsForRom(8)).toHaveLength(1);

    // A row that never reached the device is deleted server-side.
    removeShortcut.mockResolvedValue({
      data: shortcut(2, 8, "desktop", "pending_add"),
    });
    await store.remove(store.shortcutsForRom(8)[0]!);
    expect(store.shortcutsForRom(8)).toEqual([]);

    // An added row is queued for removal and stays visible until the device acks.
    removeShortcut.mockResolvedValue({
      data: shortcut(1, 7, "desktop", "pending_remove"),
    });
    await store.remove(store.shortcutsForRom(7)[0]!);
    expect(store.shortcutsForRom(7)[0]?.status).toBe("pending_remove");
  });
});
