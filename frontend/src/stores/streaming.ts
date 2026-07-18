import { defineStore } from "pinia";
import { ref, computed } from "vue";
import streamingApi from "@/services/api/streaming";
import type {
  ActiveSession,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

export type {
  ActiveSession,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

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
   * If it fails, streaming stays disabled and no buttons appear.
   */
  async function fetchConfig(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await streamingApi.fetchConfig();
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
   *   503 - broker/unreachable
   */
  async function claimSession(romId: number): Promise<ActiveSession> {
    const { data } = await streamingApi.claimSession(romId);
    activeSession.value = data;
    return data;
  }

  /**
   * Release the active session when the user leaves the player page.
   * Returns true when the backend acknowledged the release
   * (the local session record is dropped); false when the call
   * failed (the session is still held server-side, so the record is kept so
   * the user can retry instead of being wedged behind their own session).
   */
  async function releaseSession(platform: string): Promise<boolean> {
    if (!platform) return false;
    try {
      await streamingApi.releaseSession(platform);
      activeSession.value = null;
      return true;
    } catch (err) {
      console.warn("[streaming] Could not release session:", err);
      return false;
    }
  }

  /**
   * Save game state then release the session.
   * wait=true (default): blocks until broker confirms save+kill - use for explicit button press.
   * wait=false: broker fires save+kill in background, returns immediately - use for navigation away.
   * Drops the local session record only on a confirmed release so a failed
   * call doesn't leave the user wedged behind their own still-held session.
   */
  async function saveAndExit(
    platform: string,
    slot = 0,
    wait = true,
  ): Promise<boolean> {
    if (!platform) return false;
    try {
      const { data } = await streamingApi.saveAndExit(platform, slot, wait);
      activeSession.value = null;
      return data.saved ?? false;
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit:", err);
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
  };
});
