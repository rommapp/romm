import { isAxiosError } from "axios";
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import api from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StreamingContainer {
  platform: string; // e.g. "ps2"
  host: string; // browser-facing URL, e.g. "http://192.168.1.50:3000"
  label: string; // e.g. "PCSX2"
}

export interface StreamingConfig {
  enabled: boolean;
  containers: StreamingContainer[];
}

export interface ActiveSession {
  platform: string;
  host: string;
  label: string;
  rom_name: string;
  claimed_at: string;
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useStreamingStore = defineStore("streaming", () => {
  const config = ref<StreamingConfig>({ enabled: false, containers: [] });
  const activeSession = ref<ActiveSession | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isEnabled = computed(() => config.value.enabled);

  // ── Actions ────────────────────────────────────────────────────────────────

  /**
   * Returns the streaming container for a given platform slug, or null if
   * streaming is disabled or no container is configured for that platform.
   * Case-insensitive so "PS2" and "ps2" both match.
   */
  function containerForPlatform(
    slug: string | null | undefined,
  ): StreamingContainer | null {
    if (!slug || !config.value.enabled) return null;
    const lower = slug.toLowerCase();
    return (
      config.value.containers.find((c) => c.platform.toLowerCase() === lower) ??
      null
    );
  }

  /**
   * Returns per-platform save-state capabilities for the streaming player UI.
   *
   * maxSlots  - number of user-accessible save slots (slot selector range)
   * hasAutosave - whether a dedicated "load autosave" action is available
   *
   * Dolphin (ngc, wii, wiiu): slots 1-7 user-accessible; slot 8 reserved for auto-save.
   * PCSX2 (ps2), xemu (xbox): 9 slots + slot 10 autosave.
   * Eden (switch) and unknown platforms: no save state UI - a platform gets
   * slots only once its broker's slot semantics are known.
   */
  function platformCapabilities(slug: string | null | undefined): {
    maxSlots: number;
    hasAutosave: boolean;
    autosaveSlot: number;
  } {
    const lower = (slug ?? "").toLowerCase();
    if (lower === "ngc" || lower === "wii" || lower === "wiiu") {
      return { maxSlots: 7, hasAutosave: true, autosaveSlot: 8 };
    }
    if (lower === "switch") {
      return { maxSlots: 0, hasAutosave: false, autosaveSlot: 0 };
    }
    if (lower === "ps2" || lower === "xbox") {
      return { maxSlots: 9, hasAutosave: true, autosaveSlot: 10 };
    }
    return { maxSlots: 0, hasAutosave: false, autosaveSlot: 0 };
  }

  /**
   * Fetch streaming config from the backend once on app load.
   * Non-fatal - if it fails, streaming stays disabled and no buttons appear.
   */
  async function fetchConfig(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await api.get<StreamingConfig>("/streaming/config", {
        headers: { "Cache-Control": "no-cache" },
      });
      config.value = {
        enabled: data.enabled ?? false,
        containers: data.containers ?? [],
      };
    } catch (err) {
      error.value = String(err);
      console.warn("[streaming] Could not fetch config:", err);
    } finally {
      loading.value = false;
    }
  }

  /**
   * Claim a streaming session for a ROM. The backend derives the platform,
   * filesystem path, and display name from the ROM id - the client never
   * sends a path.
   * Returns the session data (including the container host URL) on success.
   * Throws an error with a `status` property on failure:
   *   409 session in use - error has who/what is playing
   *   404 - ROM or platform container not configured
   *   503 - broker unreachable
   */
  async function claimSession(romId: number): Promise<ActiveSession> {
    try {
      const { data } = await api.post<ActiveSession>("/streaming/sessions", {
        rom_id: romId,
      });
      activeSession.value = data;
      return data;
    } catch (e) {
      const response = isAxiosError(e) ? e.response : undefined;
      const detail = response?.data?.detail;
      const err = Object.assign(
        new Error(detail?.message ?? `HTTP ${response?.status}`),
        { status: response?.status, detail },
      );
      throw err;
    }
  }

  /**
   * Release the active session when the user leaves the player page.
   * Best-effort - never throws.
   */
  async function releaseSession(platform: string): Promise<void> {
    if (!platform) return;
    activeSession.value = null;
    try {
      await api.delete(`/streaming/sessions/${platform}`);
    } catch (err) {
      console.warn("[streaming] Could not release session:", err);
    }
  }

  /**
   * Save game state then release the session.
   * wait=true (default): blocks until broker confirms save+kill - use for explicit button press.
   * wait=false: broker fires save+kill in background, returns immediately - use for navigation away.
   * Best-effort - never throws.
   */
  async function saveAndExit(
    platform: string,
    slot = 0,
    wait = true,
  ): Promise<boolean> {
    if (!platform) return false;
    activeSession.value = null;
    try {
      const { data } = await api.post(
        `/streaming/sessions/${platform}/save-and-exit`,
        { slot, wait },
      );
      return data.saved ?? false;
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit:", err);
      return false;
    }
  }

  /**
   * Set emulator volume (0-100). Best-effort - never throws.
   */
  async function setVolume(platform: string, level: number): Promise<void> {
    if (!platform) return;
    try {
      await api.post(`/streaming/sessions/${platform}/volume`, {
        level: Math.round(level),
      });
    } catch (err) {
      console.warn("[streaming] Could not set volume:", err);
    }
  }

  /**
   * Toggle or explicitly set mute. Pass true/false to set, omit for toggle.
   * Best-effort - never throws.
   */
  async function setMute(platform: string, mute?: boolean): Promise<void> {
    if (!platform) return;
    try {
      await api.post(
        `/streaming/sessions/${platform}/mute`,
        mute !== undefined ? { mute } : {},
      );
    } catch (err) {
      console.warn("[streaming] Could not set mute:", err);
    }
  }

  /**
   * Save game state to a slot (1-9) without stopping the emulator.
   * The broker fires the save in the background and returns immediately.
   * Best-effort - never throws.
   */
  async function saveState(platform: string, slot = 1): Promise<boolean> {
    if (!platform) return false;
    try {
      const { data } = await api.post(
        `/streaming/sessions/${platform}/save-state`,
        { slot },
      );
      return data.status === "saving";
    } catch (err) {
      console.warn("[streaming] Could not save state:", err);
      return false;
    }
  }

  /**
   * Load game state from a slot (1-10). Slot 10 is the autosave slot on xemu and rpcs3.
   * Best-effort - never throws.
   */
  async function loadState(platform: string, slot = 1): Promise<boolean> {
    if (!platform) return false;
    try {
      const { data } = await api.post(
        `/streaming/sessions/${platform}/load-state`,
        { slot },
      );
      return data.loaded ?? false;
    } catch (err) {
      console.warn("[streaming] Could not load state:", err);
      return false;
    }
  }

  return {
    config,
    activeSession,
    loading,
    error,
    isEnabled,
    containerForPlatform,
    platformCapabilities,
    fetchConfig,
    claimSession,
    releaseSession,
    saveAndExit,
    setVolume,
    setMute,
    saveState,
    loadState,
  };
});
