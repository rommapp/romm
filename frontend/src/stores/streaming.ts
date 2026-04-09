import { defineStore } from "pinia";
import { ref, computed } from "vue";

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
   * Fetch streaming config from the backend once on app load.
   * Non-fatal — if it fails, streaming stays disabled and no buttons appear.
   */
  async function fetchConfig(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const res = await fetch("/api/streaming/config", {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data: StreamingConfig = await res.json();
      config.value = {
        enabled: data.enabled ?? false,
        containers: data.containers ?? [],
      };

      console.debug(
        "[streaming] Config loaded — enabled:",
        config.value.enabled,
        "platforms:",
        config.value.containers.map((c) => c.platform),
      );
    } catch (err) {
      error.value = String(err);
      console.warn("[streaming] Could not fetch config:", err);
    } finally {
      loading.value = false;
    }
  }

  /**
   * Claim a streaming session for a platform + ROM.
   * Returns the session data (including the container host URL) on success.
   * Throws an error with a `status` property on failure:
   *   409 session in use - error has who/what is playing
   *   404 — platform not configured
   *   503 — broker unreachable
   */
  async function claimSession(
    platform: string,
    romPath: string,
    romName: string,
  ): Promise<ActiveSession> {
    const res = await fetch("/api/streaming/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platform, rom_path: romPath, rom_name: romName }),
    });

    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      const err = Object.assign(
        new Error(detail?.detail?.message ?? `HTTP ${res.status}`),
        { status: res.status, detail: detail?.detail },
      );
      throw err;
    }

    const session: ActiveSession = await res.json();
    activeSession.value = session;
    return session;
  }

  /**
   * Release the active session when the user leaves the player page.
   * Best-effort — never throws.
   */
  async function releaseSession(platform: string): Promise<void> {
    if (!platform) return;
    activeSession.value = null;
    try {
      await fetch(`/api/streaming/sessions/${platform}`, { method: "DELETE" });
    } catch (err) {
      console.warn("[streaming] Could not release session:", err);
    }
  }

  /**
   * Save game state then release the session.
   * wait=true (default): blocks until broker confirms save+kill — use for explicit button press.
   * wait=false: broker fires save+kill in background, returns immediately — use for navigation away.
   * Best-effort — never throws.
   */
  async function saveAndExit(
    platform: string,
    slot = 0,
    wait = true,
  ): Promise<boolean> {
    if (!platform) return false;
    activeSession.value = null;
    try {
      const res = await fetch(
        `/api/streaming/sessions/${platform}/save-and-exit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot, wait }),
        },
      );
      if (!res.ok) return false;
      const data = await res.json();
      return data.saved ?? false;
    } catch (err) {
      console.warn("[streaming] Could not save-and-exit:", err);
      return false;
    }
  }

  /**
   * Set emulator volume (0–100). Best-effort — never throws.
   */
  async function setVolume(platform: string, level: number): Promise<void> {
    if (!platform) return;
    try {
      await fetch(`/api/streaming/sessions/${platform}/volume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ level: Math.round(level) }),
      });
    } catch (err) {
      console.warn("[streaming] Could not set volume:", err);
    }
  }

  /**
   * Toggle or explicitly set mute. Pass true/false to set, omit for toggle.
   * Best-effort — never throws.
   */
  async function setMute(platform: string, mute?: boolean): Promise<void> {
    if (!platform) return;
    try {
      await fetch(`/api/streaming/sessions/${platform}/mute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(mute !== undefined ? { mute } : {}),
      });
    } catch (err) {
      console.warn("[streaming] Could not set mute:", err);
    }
  }

  /**
   * Save game state to a slot (1–9) without stopping the emulator.
   * The broker fires the save in the background and returns immediately.
   * Best-effort — never throws.
   */
  async function saveState(platform: string, slot = 1): Promise<boolean> {
    if (!platform) return false;
    try {
      const res = await fetch(
        `/api/streaming/sessions/${platform}/save-state`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot }),
        },
      );
      if (!res.ok) return false;
      const data = await res.json();
      return data.status === "saving";
    } catch (err) {
      console.warn("[streaming] Could not save state:", err);
      return false;
    }
  }

  /**
   * Load game state from a slot (1–9).
   * Best-effort — never throws.
   */
  async function loadState(platform: string, slot = 1): Promise<boolean> {
    if (!platform) return false;
    try {
      const res = await fetch(
        `/api/streaming/sessions/${platform}/load-state`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot }),
        },
      );
      if (!res.ok) return false;
      const data = await res.json();
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
