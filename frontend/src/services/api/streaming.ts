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
  claimed_at: string;
  host: string;
  /** null when no resume was asked for; false means the state could not be
   *  pushed and the session started fresh. */
  resume: boolean | null;
}

/** `streaming:launch-failed`. The claim is already released. */
export interface LaunchFailed {
  platform: string;
  container: string;
  claimed_at: string;
  detail: string;
}

/** `streaming:launch-phase`, while a broker unpacks a large title. */
export interface LaunchPhase {
  platform: string;
  container: string;
  claimed_at: string;
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

/** Body of the 409 a claim returns when the container is taken. The route
 *  raises it as a plain detail dict, so it has no generated schema. */
export interface ContainerBusyDetail {
  message: string;
  draining: boolean;
  /** The game holding it, null when the caller may not see which. */
  rom_name: string | null;
  claimed_at: string | null;
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
  saveId?: number,
  memoryCardId?: number,
  cardImport?: MemoryCardImport,
  multiplayer?: boolean,
) {
  return api.post<LaunchingSession>("/streaming/sessions", {
    rom_id: romId,
    ...(stateId !== undefined ? { state_id: stateId } : {}),
    ...(saveId !== undefined ? { save_id: saveId } : {}),
    ...(memoryCardId !== undefined ? { memory_card_id: memoryCardId } : {}),
    ...(cardImport !== undefined ? { card_import: cardImport } : {}),
    ...(multiplayer !== undefined ? { multiplayer } : {}),
  });
}

async function releaseSession(
  platform: string,
  reason?: string,
  container?: string | null,
  save?: boolean,
  claimedAt?: string | null,
) {
  return api.delete(`/streaming/sessions/${platform}`, {
    params: {
      // The claim this release is for, so a tab whose claim was taken over
      // cannot end the one that replaced it. Admin releases send none.
      ...(claimedAt != null ? { claimed_at: claimedAt } : {}),
      // Sent whenever the caller supplied one, empty string included: the
      // backend treats the param's presence as "this is an admin force-release".
      ...(reason !== undefined ? { reason } : {}),
      // Names which container to release, since a pool serves one platform
      // from several: the holder names the one it claimed, an admin its pick.
      ...(container != null ? { container } : {}),
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

async function saveAndExit(
  platform: string,
  slot = 0,
  wait = true,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post(
    `/streaming/sessions/${platform}/save-and-exit`,
    { slot, wait },
    { params: { container, claimed_at: claimedAt } },
  );
}

async function heartbeatSession(
  platform: string,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<SessionStatus>(
    `/streaming/sessions/${platform}/heartbeat`,
    undefined,
    { params: { container, claimed_at: claimedAt } },
  );
}

async function sessionStatus(platform: string, claimedAt?: string | null) {
  return api.get<SessionStatus>(`/streaming/sessions/${platform}/status`, {
    params: { claimed_at: claimedAt },
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

// Names which container and which claim, so an unload cannot end the claim
// that replaced it.
function claimQuery(
  container?: string | null,
  claimedAt?: string | null,
): string {
  const params = new URLSearchParams();
  if (container) params.set("container", container);
  if (claimedAt) params.set("claimed_at", claimedAt);
  const search = params.toString();
  return search ? `?${search}` : "";
}

function saveAndExitKeepalive(
  platform: string,
  slot = 0,
  container?: string | null,
  claimedAt?: string | null,
): Promise<Response> {
  const query = claimQuery(container, claimedAt);
  return fetch(`/api/streaming/sessions/${platform}/save-and-exit${query}`, {
    method: "POST",
    keepalive: true,
    credentials: "same-origin",
    headers: keepaliveHeaders(),
    body: JSON.stringify({ slot, wait: false }),
  });
}

function releaseSessionKeepalive(
  platform: string,
  container?: string | null,
  claimedAt?: string | null,
): Promise<Response> {
  const query = claimQuery(container, claimedAt);
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
  loadState,
  swapDisc,
  adminListSessions,
  adminListContainers,
  claimDesktop,
  saveAndExitKeepalive,
  releaseSessionKeepalive,
};
