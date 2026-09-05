import type {
  AdminContainerSchema,
  AdminSessionSchema,
  LaunchingSessionSchema,
  DesktopSessionSchema,
  JoinableSessionSchema,
  JoinedSessionSchema,
  MemoryCardImportRequired,
  SessionStatusSchema,
  SessionTerminationSchema,
  SlotCapabilitiesSchema,
  StreamingConfigSchema,
  StreamingContainerSchema,
} from "@/__generated__";
import api, { keepaliveHeaders } from "@/services/api";

// ── Types ─────────────────────────────────────────────────────────────────────
//
// The shapes themselves are generated from the backend's OpenAPI schema. These
// aliases give each one the name the frontend already calls it by, so a route's
// response cannot drift from what the components consume without the typecheck
// saying so.

export type PlatformCapabilities = SlotCapabilitiesSchema;
export type StreamingContainer = StreamingContainerSchema;
export type StreamingConfig = StreamingConfigSchema;
export type LaunchingSession = LaunchingSessionSchema;

// The launch's own result arrives on the socket, and socket payloads reach no
// route so they are not in the OpenAPI schema (constitution SS X.10, backend
// debt). The backend builds each of these from a model of the same name in
// endpoints/responses/streaming.py, so the shapes stay tied.

/** `streaming:launch-ready`: the game is up, and `host` is the iframe URL. */
export interface LaunchReady {
  platform: string;
  container: string;
  host: string;
  /** null when no resume was asked for; false means the state could not be
   *  pushed and the session started fresh. */
  resume: boolean | null;
}

/** `streaming:launch-failed`. The claim is already released. */
export interface LaunchFailed {
  platform: string;
  container: string;
  detail: string;
}

/** `streaming:launch-phase`, while a broker unpacks a large title. */
export interface LaunchPhase {
  platform: string;
  container: string;
  phase: string | null;
}
export type AdminStreamingSession = AdminSessionSchema;
export type AdminStreamingContainer = AdminContainerSchema;
export type DesktopSession = DesktopSessionSchema;
export type SessionTermination = SessionTerminationSchema;
export type SessionStatus = SessionStatusSchema;
export type JoinableSession = JoinableSessionSchema;
export type JoinedSession = JoinedSessionSchema;

/** Body of the 428 a claim returns when the container still holds a memory
 *  card nobody has decided about. */
export type MemoryCardImportDetail = MemoryCardImportRequired;

/** The answer to that prompt, replayed on the retried claim. "discard" erases
 *  the card currently on the container. */
export type MemoryCardImport = "adopt" | "discard";

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

/** Answers 202 as soon as the container is reserved. The room URL arrives on
 *  the socket as `streaming:launch-ready`, so this needs no ceiling of its own
 *  beyond the client default. */
async function claimSession(
  romId: number,
  stateId?: number,
  memoryCardId?: number,
  cardImport?: MemoryCardImport,
  multiplayer?: boolean,
) {
  return api.post<LaunchingSession>("/streaming/sessions", {
    rom_id: romId,
    ...(stateId !== undefined ? { state_id: stateId } : {}),
    ...(memoryCardId !== undefined ? { memory_card_id: memoryCardId } : {}),
    ...(cardImport !== undefined ? { card_import: cardImport } : {}),
    ...(multiplayer !== undefined ? { multiplayer } : {}),
  });
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
