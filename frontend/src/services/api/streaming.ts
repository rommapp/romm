import { default as Cookies } from "js-cookie";
import api from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PlatformCapabilities {
  max_slots: number; // manual save slots, selectable as 1..max_slots
  has_autosave: boolean; // whether a dedicated autosave slot can be loaded
  autosave_slot: number; // that slot's index (loadable, not savable), 0 if none
}

export interface StreamingContainer {
  platform: string; // "ps2"
  host: string; // "http://192.168.1.50:3000"
  label: string; // "PCSX2"
  emulator: string; // state namespace, e.g. "pcsx2", matches State.emulator
  capabilities: PlatformCapabilities;
  // Whether this container syncs whole memory cards (whole-card sync). Gates
  // the memory-card picker; false/absent for containers without it.
  supports_memory_cards?: boolean;
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
  // true: resume state delivered to the broker; false: resume requested but
  // the push failed (fresh launch); null: no resume requested.
  resume: boolean | null;
}

// Entry of the admin-only GET /streaming/sessions list. Nullable fields
// cover sessions claimed before a config change (container removed) or
// records written by an older backend (no platform stored).
export interface AdminStreamingSession {
  container: string;
  label: string | null;
  platform: string | null;
  rom_id: number | null;
  rom_name: string | null;
  claimed_at: string | null;
  user_id: number | null;
  username: string | null;
}

// ── Requests ──────────────────────────────────────────────────────────────────

async function fetchConfig() {
  return api.get<StreamingConfig>("/streaming/config", {
    headers: { "Cache-Control": "no-cache" },
  });
}

async function claimSession(
  romId: number,
  stateId?: number,
  memoryCardId?: number,
) {
  return api.post<ActiveSession>("/streaming/sessions", {
    rom_id: romId,
    ...(stateId !== undefined ? { state_id: stateId } : {}),
    ...(memoryCardId !== undefined ? { memory_card_id: memoryCardId } : {}),
  });
}

async function releaseSession(platform: string) {
  return api.delete(`/streaming/sessions/${platform}`);
}

async function saveAndExit(platform: string, slot = 0, wait = true) {
  return api.post(`/streaming/sessions/${platform}/save-and-exit`, {
    slot,
    wait,
  });
}

async function heartbeatSession(platform: string) {
  return api.post(`/streaming/sessions/${platform}/heartbeat`);
}

async function setVolume(platform: string, level: number) {
  return api.post(`/streaming/sessions/${platform}/volume`, {
    level: Math.round(level),
  });
}

async function setMute(platform: string, mute?: boolean) {
  return api.post(
    `/streaming/sessions/${platform}/mute`,
    mute !== undefined ? { mute } : {},
  );
}

async function saveState(platform: string, slot = 1) {
  return api.post(`/streaming/sessions/${platform}/save-state`, { slot });
}

async function loadState(platform: string, slot = 1) {
  return api.post(`/streaming/sessions/${platform}/load-state`, { slot });
}

async function adminListSessions() {
  return api.get<{ sessions: AdminStreamingSession[] }>("/streaming/sessions");
}

// ── Unload-path requests ──────────────────────────────────────────────────────
// On pagehide the page may die before an axios request leaves, so these use
// fetch keepalive, which the browser completes after the page is gone.
// sendBeacon cannot carry the CSRF header, so the cookie-sourced header is
// set by hand (mirrors the axios interceptor).

function keepaliveHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    "x-csrftoken": Cookies.get("romm_csrftoken") ?? "",
  };
}

function saveAndExitKeepalive(platform: string, slot = 0): void {
  void fetch(`/api/streaming/sessions/${platform}/save-and-exit`, {
    method: "POST",
    keepalive: true,
    credentials: "same-origin",
    headers: keepaliveHeaders(),
    body: JSON.stringify({ slot, wait: false }),
  });
}

function releaseSessionKeepalive(platform: string): void {
  void fetch(`/api/streaming/sessions/${platform}`, {
    method: "DELETE",
    keepalive: true,
    credentials: "same-origin",
    headers: keepaliveHeaders(),
  });
}

export default {
  fetchConfig,
  claimSession,
  releaseSession,
  saveAndExit,
  heartbeatSession,
  setVolume,
  setMute,
  saveState,
  loadState,
  adminListSessions,
  saveAndExitKeepalive,
  releaseSessionKeepalive,
};
