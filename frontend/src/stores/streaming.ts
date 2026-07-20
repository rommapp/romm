import { defineStore } from "pinia";
import { ref, computed } from "vue";
import streamingApi from "@/services/api/streaming";
import type {
  ActiveSession,
  AdminStreamingSession,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

export type {
  ActiveSession,
  AdminStreamingSession,
  PlatformCapabilities,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

const NO_CAPABILITIES = {
  maxSlots: 0,
  hasAutosave: false,
  autosaveSlot: 0,
} as const;

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
   * Returns per-platform save-state capabilities for the streaming player UI,
   * sourced from the container config the backend ships in /config (the single
   * source of truth). Platforms with no configured container, or none the
   * backend gives slots to, get an empty capability set (no save-state UI).
   *
   * maxSlots    - number of user-accessible save slots (slot selector range)
   * hasAutosave - whether a dedicated "load autosave" action is available
   * autosaveSlot - the slot index used for autosave (0 when none)
   */
  function platformCapabilities(slug: string | null | undefined): {
    maxSlots: number;
    hasAutosave: boolean;
    autosaveSlot: number;
  } {
    const caps = containerForPlatform(slug)?.capabilities;
    if (!caps) return { ...NO_CAPABILITIES };
    return {
      maxSlots: caps.max_slots,
      hasAutosave: caps.has_autosave,
      autosaveSlot: caps.autosave_slot,
    };
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
   * Pass stateId to resume from a specific save state: the backend pushes
   * its file to the broker and the emulator loads it once the game is up.
   * The response's `resume` field reports whether that succeeded.
   * Pass memoryCardId to hydrate a specific memory card (else the backend
   * picks the user's newest card for the emulator, or auto-creates a blank
   * one). The chosen card is wiped-then-replaced onto the container at claim.
   * Returns the session data (including the container host URL) on success.
   * Throws the raw axios error on failure:
   *   409 session in use - response detail has who/what is playing
   *   404 - ROM or platform container not configured
   *   503 - broker/unreachable
   */
  async function claimSession(
    romId: number,
    stateId?: number,
    memoryCardId?: number,
  ): Promise<ActiveSession> {
    const { data } = await streamingApi.claimSession(
      romId,
      stateId,
      memoryCardId,
    );
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
   * released: the request succeeded, so the backend dropped the claim
   *   (it always releases on success, even when the save itself failed).
   * saved: the broker confirmed the state save.
   * released=false means the request failed and the claim may still be live -
   *   callers should fall back to releaseSession.
   */
  async function saveAndExit(
    platform: string,
    slot = 0,
    wait = true,
  ): Promise<{ released: boolean; saved: boolean }> {
    if (!platform) return { released: false, saved: false };
    try {
      const { data } = await streamingApi.saveAndExit(platform, slot, wait);
      activeSession.value = null;
      return { released: true, saved: data.saved ?? false };
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit:", err);
      return { released: false, saved: false };
    }
  }

  /**
   * Refresh the session's liveness stamp so the backend does not treat it as
   * abandoned. Called periodically while playing. Best-effort, never throws.
   */
  async function heartbeatSession(platform: string): Promise<void> {
    if (!platform) return;
    try {
      await streamingApi.heartbeatSession(platform);
    } catch (err) {
      console.warn("[streaming] Could not heartbeat session:", err);
    }
  }

  /**
   * saveAndExit for the pagehide path. Fire-and-forget via fetch keepalive:
   * the broker save+kill runs server-side to completion even though the page
   * is gone (wait=false; the backend forces a blocking save for card-sync
   * containers anyway). Best-effort, never throws.
   */
  function saveAndExitKeepalive(platform: string, slot = 0): void {
    if (!platform) return;
    activeSession.value = null;
    try {
      streamingApi.saveAndExitKeepalive(platform, slot);
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit (keepalive):", err);
    }
  }

  /**
   * releaseSession for the pagehide path. Fire-and-forget via fetch
   * keepalive. Best-effort, never throws.
   */
  function releaseSessionKeepalive(platform: string): void {
    if (!platform) return;
    activeSession.value = null;
    try {
      streamingApi.releaseSessionKeepalive(platform);
    } catch (err) {
      console.warn("[streaming] Could not release session (keepalive):", err);
    }
  }

  /**
   * List all active streaming sessions across every container. Admin only.
   * Best-effort, never throws, returns [] on failure.
   */
  async function adminListSessions(): Promise<AdminStreamingSession[]> {
    try {
      const { data } = await streamingApi.adminListSessions();
      return data.sessions ?? [];
    } catch (err) {
      console.warn("[streaming] Could not list sessions:", err);
      return [];
    }
  }

  /**
   * Force-release another user's session by platform. Admin only.
   * Does not touch local activeSession state - the target session belongs
   * to someone else. Returns whether the release succeeded.
   */
  async function adminReleaseSession(platform: string): Promise<boolean> {
    if (!platform) return false;
    try {
      await streamingApi.releaseSession(platform);
      return true;
    } catch (err) {
      console.warn("[streaming] Could not release session:", err);
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
    heartbeatSession,
    saveAndExitKeepalive,
    releaseSessionKeepalive,
    adminListSessions,
    adminReleaseSession,
  };
});
