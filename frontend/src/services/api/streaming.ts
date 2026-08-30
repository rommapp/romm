import { default as Cookies } from "js-cookie";
import api from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface PlatformCapabilities {
  max_slots: number; // manual save slots, selectable as 1..max_slots
  has_autosave: boolean; // whether a dedicated autosave slot can be loaded
  autosave_slot: number; // that slot's index, where exit saves land, 0 if none
  supports_disc_swap?: boolean; // a live swap route exists for this platform
  has_manual_disc_swap?: boolean; // no route, but the emulator's own UI can do it
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
  // Seconds the backend gives a claim before it gives up on the broker. The
  // claim request's own ceiling is derived from this.
  launch_timeout: number;
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
  // A desktop session runs no game, so rom_name is null and the row has to
  // say what it is rather than showing an empty cell.
  desktop: boolean;
  claimed_at: string | null;
  user_id: number | null;
  username: string | null;
}

// Row of the admin-only GET /streaming/containers list, one per container
// rather than per platform: a container serves many platforms but hosts one
// session, so the fleet view counts containers.
export interface AdminStreamingContainer {
  container: string; // the key release and desktop calls name
  label: string | null;
  host: string | null;
  platforms: string[];
  supports_desktop: boolean;
  // False when the configured host carries no scheme, so no broker URL can be
  // derived and the container can never be claimed.
  configured: boolean;
  session: Omit<AdminStreamingSession, "container" | "label"> | null;
}

export interface DesktopSession {
  container: string;
  platform: string;
  host: string;
  label: string;
  claimed_at: string;
}

/** Why a session the caller used to hold is gone. Present only when an admin
 *  ended it; an expired or self-released session carries no notice. */
export interface SessionTermination {
  ended_by: string | null;
  reason: string | null;
  ended_at: string | null;
  platform: string | null;
  rom_id: number | null;
  rom_name: string | null;
}

export interface SessionStatus {
  status: "active" | "ended";
  platform: string;
  termination?: SessionTermination | null;
  /** What the broker is unpacking, while a claim is still in flight. Absent
   *  once the launch has returned, and on brokers with no extraction step. */
  extraction_phase?: string | null;
}

/** Body of the 428 a claim returns when the container still holds a memory
 *  card nobody has decided about. Hand-written: FastAPI serves it as a bare
 *  `detail` dict, so it never reaches the OpenAPI schema. */
export interface MemoryCardImportDetail {
  code: "memory_card_import_required";
  outcome: "found" | "unreadable";
  /** Why the card could not be read. Present on "unreadable" only. */
  reason?: string;
  /** What the card holds. Present on "found" only. */
  summary?: {
    file_count: number;
    total_bytes: number;
    game_codes: string[];
  };
}

/** The answer to that prompt, replayed on the retried claim. "discard" erases
 *  the card currently on the container. */
export type MemoryCardImport = "adopt" | "discard";

/** Entry of GET /streaming/sessions/joinable. Nullable fields cover a session
 *  claimed before a config change removed its container. */
export interface JoinableSession {
  container: string;
  label: string | null;
  platform: string | null;
  rom_id: number | null;
  rom_name: string | null;
  host_username: string | null;
  claimed_at: string | null;
  // Cover and platform of the ROM, so a tile needs no second request.
  platform_id: number | null;
  platform_display_name: string | null;
  path_cover_small: string | null;
  path_cover_large: string | null;
  url_cover: string | null;
}

/** Answer to POST /streaming/sessions/{platform}/join. `host` is the room URL
 *  the joiner's iframe loads; no control route accepts them. */
export interface JoinedSession {
  platform: string;
  host: string;
  label: string;
  rom_id: number | null;
  rom_name: string | null;
}

export function isMemoryCardImportDetail(
  value: unknown,
): value is MemoryCardImportDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { code?: unknown }).code === "memory_card_import_required"
  );
}

// ── Requests ──────────────────────────────────────────────────────────────────

async function fetchConfig() {
  return api.get<StreamingConfig>("/streaming/config", {
    headers: { "Cache-Control": "no-cache" },
  });
}

/** Grace added to the backend's launch timeout, so a claim that runs the full
 *  server-side budget still returns the server's own error rather than dying
 *  on a bare client timeout first. */
const CLAIM_TIMEOUT_GRACE_MS = 60_000;

/** The claim blocks until the container has the game up, and a webstation
 *  broker unpacks pkg and archive ROMs before it can start the emulator. That
 *  runs far past the client default, so this one call carries its own ceiling,
 *  built from the launch_timeout /config ships. */
async function claimSession(
  romId: number,
  launchTimeoutSeconds: number,
  stateId?: number,
  memoryCardId?: number,
  cardImport?: MemoryCardImport,
  multiplayer?: boolean,
) {
  return api.post<ActiveSession>(
    "/streaming/sessions",
    {
      rom_id: romId,
      ...(stateId !== undefined ? { state_id: stateId } : {}),
      ...(memoryCardId !== undefined ? { memory_card_id: memoryCardId } : {}),
      ...(cardImport !== undefined ? { card_import: cardImport } : {}),
      ...(multiplayer !== undefined ? { multiplayer } : {}),
    },
    { timeout: launchTimeoutSeconds * 1_000 + CLAIM_TIMEOUT_GRACE_MS },
  );
}

async function releaseSession(
  platform: string,
  reason?: string,
  container?: string,
  save?: boolean,
) {
  return api.delete(`/streaming/sessions/${platform}`, {
    params: {
      // Sent whenever the caller supplied one, empty string included: the
      // backend treats the param's presence as "this is an admin force-release".
      ...(reason !== undefined ? { reason } : {}),
      // Names which container to release, needed when a pool serves the
      // platform and the admin is ending a session they do not own.
      ...(container !== undefined ? { container } : {}),
      // Only the player who deliberately stopped without saving sends this.
      // Everything else leaves it off so the backend still autosaves.
      ...(save === false ? { save: false } : {}),
    },
  });
}

async function listJoinableSessions() {
  return api.get<{ sessions: JoinableSession[] }>(
    "/streaming/sessions/joinable",
  );
}

async function joinSession(platform: string, container?: string) {
  return api.post<JoinedSession>(
    `/streaming/sessions/${platform}/join`,
    {},
    { params: container !== undefined ? { container } : {} },
  );
}

async function saveAndExit(platform: string, slot = 0, wait = true) {
  return api.post(`/streaming/sessions/${platform}/save-and-exit`, {
    slot,
    wait,
  });
}

async function heartbeatSession(platform: string) {
  return api.post<SessionStatus>(`/streaming/sessions/${platform}/heartbeat`);
}

async function sessionStatus(platform: string) {
  return api.get<SessionStatus>(`/streaming/sessions/${platform}/status`);
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

// The frame the browser grabbed off the stream canvas, held server-side until
// the state save that follows claims it as its thumbnail.
async function putStateFrame(platform: string, frame: Blob) {
  return api.post(`/streaming/sessions/${platform}/state-frame`, frame, {
    headers: { "Content-Type": "image/png" },
  });
}

async function loadState(platform: string, slot = 1) {
  return api.post(`/streaming/sessions/${platform}/load-state`, { slot });
}

async function swapDisc(platform: string, fileId: number) {
  return api.post(`/streaming/sessions/${platform}/swap-disc`, {
    file_id: fileId,
  });
}

async function adminListSessions() {
  return api.get<{ sessions: AdminStreamingSession[] }>("/streaming/sessions");
}

async function adminListContainers() {
  return api.get<{ enabled: boolean; containers: AdminStreamingContainer[] }>(
    "/streaming/containers",
    { headers: { "Cache-Control": "no-cache" } },
  );
}

async function claimDesktop(container: string) {
  return api.post<DesktopSession>("/streaming/desktop", { container });
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

function saveAndExitKeepalive(platform: string, slot = 0): Promise<Response> {
  return fetch(`/api/streaming/sessions/${platform}/save-and-exit`, {
    method: "POST",
    keepalive: true,
    credentials: "same-origin",
    headers: keepaliveHeaders(),
    body: JSON.stringify({ slot, wait: false }),
  });
}

function releaseSessionKeepalive(
  platform: string,
  container?: string,
): Promise<Response> {
  // Names which container to release, for the platforms a pool serves.
  const query = container ? `?container=${encodeURIComponent(container)}` : "";
  return fetch(`/api/streaming/sessions/${platform}${query}`, {
    method: "DELETE",
    keepalive: true,
    credentials: "same-origin",
    headers: keepaliveHeaders(),
  });
}

export default {
  fetchConfig,
  claimSession,
  listJoinableSessions,
  joinSession,
  releaseSession,
  saveAndExit,
  heartbeatSession,
  sessionStatus,
  setVolume,
  setMute,
  saveState,
  putStateFrame,
  loadState,
  swapDisc,
  adminListSessions,
  adminListContainers,
  claimDesktop,
  saveAndExitKeepalive,
  releaseSessionKeepalive,
};
