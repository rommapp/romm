import type {
  InstallCandidatesSchema,
  InstallDashboardSchema,
  InstallFilesSchema,
  InstallSessionSchema,
  InstallSessionState,
  InstallStreamManifestSchema,
  InstallWorkerStatusSchema,
  ProtonBuildSchema,
} from "@/__generated__";
import api from "@/services/api";
import { triggerFileDownload } from "@/services/api/rom";

// Locally defined response shapes for new Proton download endpoints. Once the
// backend types are regenerated from the OpenAPI schema, these can be moved
// back to @/__generated__.
type ProtonDownloadResponseSchema = {
  job_id: string;
};
type ProtonDownloadProgressSchema = {
  progress: number | null;
  extracting: boolean;
};

export type ProtonBuildExtended = ProtonBuildSchema & {
  version?: string | null;
  path?: string | null;
  source?: string;
  size_bytes?: number | null;
  custom?: boolean;
};
export type InstallCacheEntry = {
  session_id: number;
  rom_id: number;
  rom_name: string | null;
  platform_slug: string | null;
  user_id: number;
  state: InstallSessionState;
  size_bytes: number;
  created_at: string;
  updated_at: string;
  expires_at?: string | null;
};
export type InstallCache = {
  total_bytes: number;
  entries: InstallCacheEntry[];
};
export type InstallCacheClearResult = {
  removed: number;
  freed_bytes: number;
  skipped: number;
};

export const installApi = api;

/** Without `source`: the ROM's own installer candidates. With `source` (an
 *  archive or disc image from those): the executables inside it. */
async function getInstallCandidates(romId: number, source?: string) {
  return api.get<InstallCandidatesSchema>(`/roms/${romId}/install/candidates`, {
    params: source ? { source } : undefined,
  });
}

async function startInstall({
  romId,
  installerPath,
  sourcePath,
  protonBuild,
  ttlSeconds,
  autoMode,
}: {
  romId: number;
  installerPath?: string;
  sourcePath?: string;
  protonBuild?: string;
  ttlSeconds?: number;
  autoMode?: boolean;
}) {
  return api.post<InstallSessionSchema>(`/roms/${romId}/install`, {
    installer_path: installerPath ?? null,
    source_path: sourcePath ?? null,
    proton_build: protonBuild ?? null,
    ttl_seconds: ttlSeconds ?? null,
    auto_mode: autoMode ?? null,
  });
}

/** Flip the experimental auto mode (OCR clicks through the installer's
 *  dialogs) on a session, also while the installer is running. */
async function setInstallAutoMode(romId: number, enabled: boolean) {
  return api.patch<InstallSessionSchema>(`/roms/${romId}/install/auto-mode`, {
    enabled,
  });
}

async function getInstallSession(romId: number) {
  return api.get<InstallSessionSchema>(`/roms/${romId}/install`);
}

async function clearInstallCache(romId: number) {
  return api.delete(`/roms/${romId}/install`);
}

async function cancelInstall(romId: number, { clearCache = true } = {}) {
  return api.post<InstallSessionSchema>(
    `/roms/${romId}/install/cancel?clear_cache=${clearCache}`,
  );
}

/** Whether an install-sandbox worker is connected right now - drives whether
 *  the client offers "Install" at all. No on/off setting to check instead. */
async function getInstallWorkerStatus() {
  return api.get<InstallWorkerStatusSchema>("/roms/install/worker-status");
}

async function getInstallFiles(romId: number) {
  return api.get<InstallFilesSchema>(`/roms/${romId}/install/files`);
}

/** Proton builds the server knows about - installed (discovered on disk)
 *  and downloadable (upstream release APIs, or added by the user) alike. */
async function getProtonBuilds() {
  return api.get<{ builds: ProtonBuildExtended[] }>(
    "/roms/install/proton-builds",
  );
}

async function addCustomProtonBuild(name: string, url: string) {
  return api.post<ProtonBuildExtended>("/roms/install/proton-builds/custom", {
    name,
    url,
  });
}

async function deleteCustomProtonBuild(buildId: string) {
  return api.delete(`/roms/install/proton-builds/custom/${buildId}`);
}

/** Every install cache on disk plus the total (admin Settings view). */
async function getInstallCache() {
  return api.get<InstallCache>("/roms/install/cache");
}

async function deleteInstallCache(sessionId: number) {
  return api.delete<InstallCacheClearResult>(
    `/roms/install/cache/${sessionId}`,
  );
}

async function deleteAllInstallCaches() {
  return api.delete<InstallCacheClearResult>("/roms/install/cache");
}

/** Enqueue a Proton build download on the install worker. Returns the RQ
 *  job id to poll for completion via getProtonDownloadProgress. Only
 *  downloadable (not-yet-installed) builds can be requested. */
async function downloadProtonBuild(buildId: string) {
  return api.post<ProtonDownloadResponseSchema>(
    `/roms/install/proton/${buildId}/download`,
  );
}

/** Download progress (0.0-1.0) for a Proton build, or null when no download
 *  is in progress. */
async function getProtonDownloadProgress(buildId: string) {
  return api.get<ProtonDownloadProgressSchema>(
    `/roms/install/proton/${buildId}/progress`,
  );
}

/** This user's install sessions worth surfacing on Home (still active, or
 *  finished with a cache still on disk). Backs the "Active Installers"
 *  widget, which only renders when this list is non-empty. */
async function getInstallDashboard() {
  return api.get<InstallDashboardSchema>("/roms/install/dashboard");
}

/** Relative download path for one installed file, ready for a plain `<a href>`. */
function getInstallFileDownloadPath(romId: number, filePath: string): string {
  return `/api/roms/${romId}/install/files/${encodeURI(filePath)}`;
}

/** Download a finished install's entire cache as one ZIP - same
 *  fire-and-forget `<a>`-click pattern as romApi.downloadRom/bulkDownloadRoms
 *  (the browser follows the URL and streams the response directly, no
 *  fetch/blob handling needed here). */
function downloadInstallCache(romId: number) {
  return triggerFileDownload(`/api/roms/${romId}/install/download`);
}

/** Live view of an install's output (sealed/complete per file, viewer count,
 *  the shared bandwidth cap) - one endpoint regardless of whether the
 *  session is still running or already finished. */
async function getInstallStreamManifest(romId: number) {
  return api.get<InstallStreamManifestSchema>(
    `/roms/${romId}/install/stream/manifest`,
  );
}

/** Relative download path for one file that may still be installing - a
 *  plain `<a href>`/browser download against this Range-resumes as more of
 *  the file seals, the same way it would for an already-finished one. */
function getInstallStreamFileDownloadPath(
  romId: number,
  filePath: string,
): string {
  return `/api/roms/${romId}/install/stream/${encodeURI(filePath)}`;
}

export default {
  getInstallCandidates,
  startInstall,
  setInstallAutoMode,
  getInstallSession,
  clearInstallCache,
  cancelInstall,
  getInstallWorkerStatus,
  getInstallDashboard,
  getInstallFiles,
  getInstallFileDownloadPath,
  downloadInstallCache,
  getInstallStreamManifest,
  getInstallStreamFileDownloadPath,
  getProtonBuilds,
  addCustomProtonBuild,
  deleteCustomProtonBuild,
  getInstallCache,
  deleteInstallCache,
  deleteAllInstallCaches,
  downloadProtonBuild,
  getProtonDownloadProgress,
};
