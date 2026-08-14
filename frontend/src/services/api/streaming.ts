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
  capabilities: PlatformCapabilities;
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

// ── Requests ──────────────────────────────────────────────────────────────────

async function fetchConfig() {
  return api.get<StreamingConfig>("/streaming/config", {
    headers: { "Cache-Control": "no-cache" },
  });
}

async function claimSession(romId: number) {
  return api.post<ActiveSession>("/streaming/sessions", { rom_id: romId });
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

export default {
  fetchConfig,
  claimSession,
  releaseSession,
  saveAndExit,
  setVolume,
  setMute,
  saveState,
  loadState,
};
