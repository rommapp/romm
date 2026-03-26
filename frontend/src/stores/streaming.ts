import { defineStore } from "pinia";
import { ref, computed } from "vue";

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

export const useStreamingStore = defineStore("streaming", () => {
  const config = ref<StreamingConfig>({ enabled: false, containers: [] });
  const activeSession = ref<ActiveSession | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  const isEnabled = computed(() => config.value.enabled);

  /**
   * Returns the container config for a given platform slug, or null if
   * streaming is disabled or no container is configured for that platform.
   * Components use this to decide whether to show the stream play button.
   */
  function containerForPlatform(slug: string): StreamingContainer | null {
    if (!config.value.enabled) return null;
    return config.value.containers.find((c) => c.platform === slug) ?? null;
  }

  async function fetchConfig(): Promise<void> {
    try {
      const response = await fetch("/api/streaming/config", {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });

      if (!response.ok) throw new Error("Failed to fetch");

      const data = await response.json();
      this.config = data;
      this.enabled = data.enabled ?? false;
      this.containers = data.containers || [];

      console.log("Streaming config loaded:", this.enabled, this.containers); // debug
    } catch (error) {
      console.error("Failed to fetch streaming config:", error);
    }
  }

  /**
   * Claim a streaming session for a platform + ROM.
   * Returns the session data (including the container host URL) on success.
   * Throws an error with a `status` property on failure:
   *   409 session in use - error has who/what is playing
   *   404 platform not configured
   *   500 trigger write failed
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
        {
          status: res.status,
          detail: detail?.detail,
        },
      );
      throw err;
    }

    const session: ActiveSession = await res.json();
    activeSession.value = session;
    return session;
  }

  //Release the active session when the user leaves the player page.

  async function releaseSession(platform: string): Promise<void> {
    activeSession.value = null;
    try {
      await fetch(`/api/streaming/sessions/${platform}`, { method: "DELETE" });
    } catch (err) {
      // Best effort - don't block navigation if this fails
      console.warn("[streaming] Could not release session:", err);
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
  };
});
