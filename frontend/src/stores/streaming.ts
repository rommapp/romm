import { defineStore } from "pinia";
import { ref, computed } from "vue";
import streamingApi from "@/services/api/streaming";
import type {
  ActiveSession,
  JoinableSession,
  JoinedSession,
  MemoryCardImport,
  SessionStatus,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

export type {
  ActiveSession,
  AdminStreamingSession,
  JoinableSession,
  JoinedSession,
  MemoryCardImport,
  MemoryCardImportDetail,
  PlatformCapabilities,
  SessionStatus,
  SessionTermination,
  StreamingConfig,
  StreamingContainer,
} from "@/services/api/streaming";

const NO_CAPABILITIES = {
  maxSlots: 0,
  hasAutosave: false,
  autosaveSlot: 0,
  supportsDiscSwap: false,
  hasManualDiscSwap: false,
} as const;

// ── Store ─────────────────────────────────────────────────────────────────────

export const useStreamingStore = defineStore("streaming", () => {
  // The launch timeout stands in until /config answers, and covers a backend
  // too old to ship one. It matches that route's own default.
  const DEFAULT_LAUNCH_TIMEOUT_SECONDS = 600;

  const config = ref<StreamingConfig>({
    enabled: false,
    containers: [],
    launch_timeout: DEFAULT_LAUNCH_TIMEOUT_SECONDS,
  });
  const activeSession = ref<ActiveSession | null>(null);
  const loading = ref(false);
  // `loading` is false both before and after the fetch, so consumers that must
  // not act on an unresolved config need this instead.
  const configLoaded = ref(false);
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
   * supportsDiscSwap - whether the disc can be changed mid-session
   * hasManualDiscSwap - whether the emulator's own UI can change it instead
   */
  function platformCapabilities(slug: string | null | undefined): {
    maxSlots: number;
    hasAutosave: boolean;
    autosaveSlot: number;
    supportsDiscSwap: boolean;
    hasManualDiscSwap: boolean;
  } {
    const caps = containerForPlatform(slug)?.capabilities;
    if (!caps) return { ...NO_CAPABILITIES };
    return {
      maxSlots: caps.max_slots,
      hasAutosave: caps.has_autosave,
      autosaveSlot: caps.autosave_slot,
      supportsDiscSwap: caps.supports_disc_swap ?? false,
      hasManualDiscSwap: caps.has_manual_disc_swap ?? false,
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
        launch_timeout: data.launch_timeout ?? DEFAULT_LAUNCH_TIMEOUT_SECONDS,
      };
    } catch (err) {
      error.value = String(err);
      console.warn("[streaming] Could not fetch config:", err);
    } finally {
      loading.value = false;
      configLoaded.value = true;
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
   *   428 - the container's pre-existing memory card needs a decision;
   *         retry with cardImport set to the user's answer
   *   503 - broker/unreachable
   */
  async function claimSession(
    romId: number,
    stateId?: number,
    memoryCardId?: number,
    cardImport?: MemoryCardImport,
    multiplayer?: boolean,
  ): Promise<ActiveSession> {
    const { data } = await streamingApi.claimSession(
      romId,
      config.value.launch_timeout,
      stateId,
      memoryCardId,
      cardImport,
      multiplayer,
    );
    activeSession.value = data;
    return data;
  }

  // Populated on demand by surfaces that offer a Join affordance. Kept in the
  // store rather than fetched per component: a virtualised gallery hosts many
  // GameActions instances, and one request each would be a request storm.
  const joinableSessions = ref<JoinableSession[]>([]);
  let joinableRequest: Promise<void> | null = null;
  let joinableFetchedAt = 0;
  // A host can end a session at any time, so the list is only trusted for as
  // long as a user takes to scan a page before acting on it.
  const JOINABLE_MAX_AGE_MS = 30_000;

  /**
   * Refresh the whole-library list of joinable sessions.
   *
   * Whole-library rather than per-ROM: a gallery card offers Join for its own
   * ROM and cannot fetch for itself. Concurrent callers share the one in-flight
   * request, which is also what keeps an older response from landing last and
   * overwriting a newer one. `force` skips the freshness window, for a surface
   * the user is about to act on.
   */
  async function fetchJoinableSessions(force = false): Promise<void> {
    if (joinableRequest) return joinableRequest;
    if (!force && Date.now() - joinableFetchedAt < JOINABLE_MAX_AGE_MS) return;

    joinableRequest = (async () => {
      try {
        const { data } = await streamingApi.listJoinableSessions();
        joinableSessions.value = data.sessions;
      } catch {
        // Best effort, and the last known list stays: a failed refresh says
        // nothing about which sessions are still up, and wiping it would pull
        // the Join affordance off every card the user is looking at.
      } finally {
        joinableFetchedAt = Date.now();
        joinableRequest = null;
      }
    })();
    return joinableRequest;
  }

  /**
   * Drop a session the caller has just found to be gone, so the Join
   * affordance disappears instead of waiting out the freshness window.
   */
  function forgetJoinableSession(romId: number): void {
    joinableSessions.value = joinableSessions.value.filter(
      (s) => s.rom_id !== romId,
    );
  }

  function joinableForRom(
    romId: number | null | undefined,
  ): JoinableSession | null {
    if (romId == null) return null;
    return joinableSessions.value.find((s) => s.rom_id === romId) ?? null;
  }

  /**
   * Ask to join a session someone else opened to other players. Returns the
   * room URL for the joiner's iframe. Unlike claimSession this grants no
   * control of the container: every control route stays with the host.
   */
  async function joinSession(
    platform: string,
    container?: string,
  ): Promise<JoinedSession> {
    const { data } = await streamingApi.joinSession(platform, container);
    return data;
  }

  /**
   * Release the active session when the user leaves the player page.
   * Returns true when the backend acknowledged the release
   * (the local session record is dropped); false when the call
   * failed (the session is still held server-side, so the record is kept so
   * the user can retry instead of being wedged behind their own session).
   * save=false is a player leaving deliberately without saving; it stays on
   * by default so the tab-close path keeps autosaving.
   */
  async function releaseSession(
    platform: string,
    save = true,
  ): Promise<boolean> {
    if (!platform) return false;
    try {
      await streamingApi.releaseSession(platform, undefined, undefined, save);
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
   * released: the backend gave the container back (it does so even when the
   *   save itself failed), and reports when it could not.
   * saved: the broker confirmed the state save.
   * released=false means the claim may still be live - callers should fall
   * back to releaseSession.
   */
  async function saveAndExit(
    platform: string,
    slot = 0,
    wait = true,
  ): Promise<{ released: boolean; saved: boolean }> {
    if (!platform) return { released: false, saved: false };
    try {
      const { data } = await streamingApi.saveAndExit(platform, slot, wait);
      const released = data.released ?? true;
      if (released) activeSession.value = null;
      return { released, saved: data.saved ?? false };
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit:", err);
      return { released: false, saved: false };
    }
  }

  /**
   * Refresh the session's liveness stamp so the backend does not treat it as
   * abandoned, and report back whether the session still exists. Called
   * periodically while playing.
   *
   * Returns null when the answer is unknown (network error): the caller must
   * not tear the player down on a transient failure, only on a definite
   * `ended`. Best-effort, never throws.
   */
  async function heartbeatSession(
    platform: string,
  ): Promise<SessionStatus | null> {
    if (!platform) return null;
    try {
      const { data } = await streamingApi.heartbeatSession(platform);
      return data;
    } catch (err) {
      console.warn("[streaming] Could not heartbeat session:", err);
      return null;
    }
  }

  /**
   * Ask whether this platform's session is still ours, without refreshing it.
   * Used on mount and on tab refocus, where a heartbeat would wrongly extend a
   * claim we may no longer hold. Null means unknown, as above.
   */
  async function fetchSessionStatus(
    platform: string,
  ): Promise<SessionStatus | null> {
    if (!platform) return null;
    try {
      const { data } = await streamingApi.sessionStatus(platform);
      return data;
    } catch (err) {
      console.warn("[streaming] Could not fetch session status:", err);
      return null;
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
    // The caller is unloading and cannot await, so the rejection is caught on
    // the promise itself; try/catch here would only see a synchronous throw.
    streamingApi.saveAndExitKeepalive(platform, slot).catch((err) => {
      console.warn("[streaming] Could not save-and-exit (keepalive):", err);
    });
  }

  /**
   * releaseSession for the pagehide path. Fire-and-forget via fetch
   * keepalive. Best-effort, never throws.
   */
  function releaseSessionKeepalive(platform: string): void {
    if (!platform) return;
    activeSession.value = null;
    streamingApi.releaseSessionKeepalive(platform).catch((err) => {
      console.warn("[streaming] Could not release session (keepalive):", err);
    });
  }

  return {
    config,
    activeSession,
    loading,
    configLoaded,
    error,
    isEnabled,
    containerForPlatform,
    platformCapabilities,
    fetchConfig,
    claimSession,
    joinableSessions,
    fetchJoinableSessions,
    forgetJoinableSession,
    joinableForRom,
    joinSession,
    releaseSession,
    saveAndExit,
    heartbeatSession,
    fetchSessionStatus,
    saveAndExitKeepalive,
    releaseSessionKeepalive,
  };
});
