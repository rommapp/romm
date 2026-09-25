import type {
  AdminContainerSchema,
  AdminContainersResponse,
  AdminSessionSchema,
  AdminSessionsResponse,
  ClaimStreamingSessionRequest,
  ContainerBusyDetail,
  LaunchingSessionSchema,
  DesktopSessionSchema,
  JoinableSessionSchema,
  JoinableSessionsResponse,
  JoinedSessionSchema,
  LaunchFailedPayload,
  LaunchPhasePayload,
  LaunchReadyPayload,
  LoadStateResponse,
  MemoryCardImportRequired,
  MuteResponse,
  ReleaseSessionResponse,
  SaveAndExitResponse,
  SaveStateResponse,
  SessionStatusSchema,
  SessionTerminationSchema,
  SlotCapabilitiesSchema,
  StreamingConfigSchema,
  StreamingContainerSchema,
  SwapDiscResponse,
  VolumeResponse,
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

// Socket payloads reach no route, so the backend publishes them into the
// schema by hand (utils/openapi.py).
export type LaunchReady = LaunchReadyPayload;
export type LaunchFailed = LaunchFailedPayload;
export type LaunchPhase = LaunchPhasePayload;

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
export type MemoryCardImport = NonNullable<
  ClaimStreamingSessionRequest["card_import"]
>;

export function isMemoryCardImportDetail(
  value: unknown,
): value is MemoryCardImportDetail {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { code?: unknown }).code === "memory_card_import_required"
  );
}

/** Body of the 409 a claim returns when the container is taken. */
export type { ContainerBusyDetail };

/** The query naming a claim by its container and the stamp it was taken at. */
function claimParams(
  container?: string | null,
  claimedAt?: string | null,
): { container?: string; claimed_at?: string } {
  return {
    ...(container != null ? { container } : {}),
    ...(claimedAt != null ? { claimed_at: claimedAt } : {}),
  };
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
  return api.delete<ReleaseSessionResponse>(`/streaming/sessions/${platform}`, {
    params: {
      // The holder names its container and stamp so a taken-over tab cannot end
      // the claim that replaced it. An admin names its pick and no stamp.
      ...claimParams(container, claimedAt),
      // Sent whenever the caller supplied one, empty string included: the
      // backend treats the param's presence as "this is an admin force-release".
      ...(reason !== undefined ? { reason } : {}),
      // Only the player who deliberately stopped without saving sends this.
      // Everything else leaves it off so the backend still autosaves.
      ...(save === false ? { save: false } : {}),
    },
  });
}

async function listJoinableSessions() {
  return api.get<JoinableSessionsResponse>("/streaming/sessions/joinable");
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
  return api.post<SaveAndExitResponse>(
    `/streaming/sessions/${platform}/save-and-exit`,
    { slot, wait },
    { params: claimParams(container, claimedAt) },
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
    { params: claimParams(container, claimedAt) },
  );
}

async function sessionStatus(platform: string, claimedAt?: string | null) {
  return api.get<SessionStatus>(`/streaming/sessions/${platform}/status`, {
    params: { claimed_at: claimedAt },
  });
}

async function setVolume(
  platform: string,
  level: number,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<VolumeResponse>(
    `/streaming/sessions/${platform}/volume`,
    { level: Math.round(level) },
    { params: claimParams(container, claimedAt) },
  );
}

async function setMute(
  platform: string,
  mute?: boolean,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<MuteResponse>(
    `/streaming/sessions/${platform}/mute`,
    mute !== undefined ? { mute } : {},
    { params: claimParams(container, claimedAt) },
  );
}

async function saveState(
  platform: string,
  slot = 1,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<SaveStateResponse>(
    `/streaming/sessions/${platform}/save-state`,
    { slot },
    { params: claimParams(container, claimedAt) },
  );
}

async function loadState(
  platform: string,
  slot = 1,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<LoadStateResponse>(
    `/streaming/sessions/${platform}/load-state`,
    { slot },
    { params: claimParams(container, claimedAt) },
  );
}

async function swapDisc(
  platform: string,
  fileId: number,
  container?: string | null,
  claimedAt?: string | null,
) {
  return api.post<SwapDiscResponse>(
    `/streaming/sessions/${platform}/swap-disc`,
    { file_id: fileId },
    { params: claimParams(container, claimedAt) },
  );
}

async function adminListSessions() {
  return api.get<AdminSessionsResponse>("/streaming/sessions");
}

async function adminListContainers() {
  return api.get<AdminContainersResponse>("/streaming/containers", {
    headers: { "Cache-Control": "no-cache" },
  });
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
  const search = new URLSearchParams(
    Object.entries(claimParams(container, claimedAt)).filter(
      ([, value]) => value,
    ),
  ).toString();
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
