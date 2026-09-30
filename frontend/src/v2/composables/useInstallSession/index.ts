// useInstallSession — state machine backing the "Install" / "Installing…"
// button on Windows ROMs (GameDetails' GameActions row) and the full-page
// /rom/:id/install view.
//
// Lifecycle: idle -> starting -> polling (DETECTING/AWAITING_INSTALLER/
// INSTALLING/STREAMING) -> settled (DONE/FAILED/EXPIRED, or no session at
// all). The VNC viewport on the Install page only ever renders while
// polling sees state === "installing" (vnc_url set).
//
// Deliberately scoped to a single ROM view, not `useGameActions`: install
// state is asynchronous and polled, which would be wasteful re-instantiated
// per card in a virtualised gallery grid (see useGameActions' own comment on
// why it stays cheap-per-card). Mounted once by GameActions' InstallButton
// (for the ribbon control) and once by the Install page (for the full
// controls) - each gets its own independent poll loop.
import { computed, onScopeDispose, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { Router } from "vue-router";
import type {
  InstallCandidateSchema,
  InstallSessionSchema,
  InstallSessionState,
} from "@/__generated__";
import { ROUTES } from "@/plugins/router";
import installApi from "@/services/api/install";
import type { ProtonBuildExtended } from "@/services/api/install";
import storeAuth from "@/stores/auth";
import type { Config } from "@/stores/config";
import storeConfig from "@/stores/config";
import type { SimpleRom } from "@/stores/roms";
import { useConfirm } from "@/v2/composables/useConfirm";
import { useIsAlive } from "@/v2/composables/useIsAlive";
import { useSnackbar } from "@/v2/composables/useSnackbar";

export type { ProtonBuildExtended };

const RUNNING_STATES: InstallSessionState[] = ["installing", "streaming"];
// A session parked here never actually ran anything yet - it's still
// waiting on the client to supply (or auto-pick) an installer path.
const AWAITING_PICK_STATES: InstallSessionState[] = [
  "detecting",
  "awaiting_installer",
];
const ACTIVE_STATES: InstallSessionState[] = [
  ...AWAITING_PICK_STATES,
  ...RUNNING_STATES,
];

const POLL_INTERVAL_MS = 3000;

// The backend's error detail (e.g. "No install worker is currently
// connected...") is far more useful than a generic "failed" toast — surface
// it when axios gives us one, same fallback chain used elsewhere in the app.
function errorDetail(err: unknown): string {
  const e = err as {
    response?: { data?: { detail?: string }; statusText?: string };
    message?: string;
  };
  return (
    e?.response?.data?.detail ||
    e?.response?.statusText ||
    e?.message ||
    "unknown error"
  );
}

// A freshly (re)started install-sandbox worker takes real, bounded time to
// come up - Wine/Proton warmup then Redis registration (see
// docker/init_scripts/install-sandbox-entrypoint.sh) - before it's visible to
// has_install_worker(). Visiting /install (or clicking "Install") right as
// the stack comes up used to hard-fail on that transient window (503 "No
// install worker is currently connected…") instead of riding it out. ~50s
// total, loosely matching the worker's own up-to-90s prefix-warmup budget.
const WORKER_STARTUP_RETRY_DELAYS_MS = [
  2000, 3000, 5000, 5000, 5000, 10000, 10000, 10000,
];

function isWorkerUnavailable(err: unknown): boolean {
  return (err as { response?: { status?: number } })?.response?.status === 503;
}

/** Retry `fn` while it fails specifically with "worker not connected yet",
 *  waiting between attempts; any other error (or exhausting the retry
 *  budget) rethrows immediately. `onWaiting` toggles around each wait so
 *  the caller can show a distinct "starting up…" state instead of a bare
 *  spinner. `shouldStop` is checked before every retry so an unmounted
 *  caller doesn't keep scheduling timers (same idiom as the poll loops
 *  below). */
async function withWorkerStartupRetry<T>(
  fn: () => Promise<T>,
  {
    onWaiting,
    shouldStop,
  }: { onWaiting?: (w: boolean) => void; shouldStop?: () => boolean } = {},
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      const result = await fn();
      onWaiting?.(false);
      return result;
    } catch (err) {
      const delay = WORKER_STARTUP_RETRY_DELAYS_MS[attempt];
      if (!isWorkerUnavailable(err) || delay === undefined || shouldStop?.()) {
        onWaiting?.(false);
        throw err;
      }
      onWaiting?.(true);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
}

export function useInstallSession(getRom: () => SimpleRom | null | undefined) {
  const { t } = useI18n();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const auth = storeAuth();
  const configStore = storeConfig();

  const session = ref<InstallSessionSchema | null>(null);
  const candidates = ref<InstallCandidateSchema[]>([]);
  // Executables inside the currently selected archive/disc image source.
  const sourceCandidates = ref<InstallCandidateSchema[]>([]);
  const loadingSourceCandidates = ref(false);
  const protonBuilds = ref<ProtonBuildExtended[]>([]);
  const streamCopy = ref(false);
  const checking = ref(false);
  const starting = ref(false);
  const cancelling = ref(false);
  const clearingCache = ref(false);
  // Whether an install-sandbox worker is connected right now - there's no
  // static setting, this is the sole signal for offering "Install" at all.
  // `null` = not checked yet (assume no, matches the fail-closed default).
  const workerAvailable = ref<boolean | null>(null);
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  // schedulePoll() runs inside an async `finally`, so a plain "clear
  // whatever timer id we're tracking" on unmount can miss a call that's
  // already in flight - it resolves anyway and reschedules regardless.
  // Checked right before every reschedule so an in-flight call becomes a
  // no-op once the consumer has unmounted. useIsAlive (onScopeDispose)
  // rather than a local flag + onBeforeUnmount, so this still works if
  // useInstallSession is ever called from inside another composable, not
  // just directly from a component's setup().
  const alive = useIsAlive();

  const canInstall = computed(() => auth.scopes.includes("roms.install"));

  const state = computed<InstallSessionState | null>(
    () => session.value?.state ?? null,
  );
  const isRunning = computed(
    () => !!state.value && RUNNING_STATES.includes(state.value),
  );
  const isActive = computed(
    () => !!state.value && ACTIVE_STATES.includes(state.value),
  );
  // True while the session is parked waiting on a human to pick/confirm an
  // installer (server-side auto-pick found nothing confident enough - see
  // start_install_session's own docstring on "manual mode"). The Install
  // page keeps its picker/CTA usable in this state instead of locking them
  // behind a permanent spinner+"Abort" the way a genuinely running session
  // does.
  const awaitingInstallerPick = computed(
    () => !!state.value && AWAITING_PICK_STATES.includes(state.value),
  );
  // "View install" only makes sense while the sandbox's VNC bridge is up.
  const vncUrl = computed(() =>
    state.value === "installing" ? session.value?.vnc_url : null,
  );
  // Excludes AWAITING_PICK_STATES too, not just isRunning: a session parked
  // there (e.g. one still waiting on an installer path) never produced any
  // files, so it has nothing to "reinstall" from - only a session that
  // actually ran (and finished, failed, or expired) does.
  const hasCache = computed(
    () =>
      !!session.value &&
      !isRunning.value &&
      !!state.value &&
      !AWAITING_PICK_STATES.includes(state.value),
  );

  // Experimental auto mode (OCR clicks through the installer's dialogs). Before
  // a session exists this is the choice sent with the start request (default
  // from the settings); once one exists the session's flag is the truth and
  // flipping it also reaches a running installer.
  const pendingAutoMode = ref(
    (configStore.config as Config).INSTALL_AUTO_MODE ?? false,
  );
  const autoMode = computed(
    () => session.value?.auto_mode ?? pendingAutoMode.value,
  );
  const autoStatus = computed(() => session.value?.auto_status ?? null);
  const autoDetail = computed(() => session.value?.auto_detail ?? null);

  async function setAutoMode(enabled: boolean) {
    const rom = getRom();
    pendingAutoMode.value = enabled;
    if (!rom || !session.value || !isActive.value) return;
    try {
      const { data } = await installApi.setInstallAutoMode(rom.id, enabled);
      session.value = data;
    } catch (err) {
      snackbar.error(
        t("rom.install-auto-mode-failed", { detail: errorDetail(err) }),
        { icon: "mdi-alert-circle-outline" },
      );
    }
  }

  // Auto mode found nothing it can press: tell the user to continue by hand.
  watch(autoStatus, (status, previous) => {
    if (status === "needs_manual" && previous !== "needs_manual") {
      snackbar.warning(t("rom.install-auto-mode-needs-manual"), {
        icon: "mdi-hand-back-right-outline",
        timeout: 10000,
      });
    }
  });

  // While the worker is bootstrapping (downloading/installing the Proton
  // build before the VNC bridge comes up), poll its download progress so the
  // Install page can show "Downloading Proton X… xx%" instead of a bare
  // spinner with no context.
  // What the worker is doing to unpack an archive/disc image before the
  // installer window exists ("extracting"/"mounting" + the file name).
  const phase = computed(() => session.value?.phase ?? null);
  const phaseDetail = computed(() => session.value?.phase_detail ?? null);
  const protonDownloadProgress = ref<number | null>(null);
  const protonDownloadLabel = ref<string | null>(null);
  // Whether the build is in the extraction phase (download complete, tarball
  // being unpacked). The frontend shows "Installing Proton…" in this state.
  const protonExtracting = ref(false);
  // True while startWithPath is retrying through a transient "worker not
  // connected yet" 503 (see withWorkerStartupRetry) - lets the Install page
  // show "waiting for the install worker to start…" instead of a bare
  // spinner during that window.
  const waitingForWorker = ref(false);

  function stopPolling() {
    if (pollTimer !== null) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  function schedulePoll() {
    stopPolling();
    if (!alive.value) return;
    pollTimer = setTimeout(refreshSession, POLL_INTERVAL_MS);
  }

  async function refreshSession() {
    const rom = getRom();
    if (!rom) return;
    try {
      const { data } = await installApi.getInstallSession(rom.id);
      session.value = data;

      // While the worker is bootstrapping (state=installing, no VNC URL yet),
      // the Proton build it picked may still be downloading. Poll the
      // download-progress endpoint so the UI can show a percentage instead of
      // a bare spinner. Once the VNC bridge is up, stop polling.
      if (
        data.state === "installing" &&
        data.vnc_url === null &&
        data.proton_build
      ) {
        pollProtonDownload(data.proton_build);
      } else {
        protonDownloadProgress.value = null;
        protonDownloadLabel.value = null;
      }
    } catch (err) {
      // Only a real 404 means "no session for this rom/user" - anything
      // else (a dropped connection, a 5xx, the backend mid-restart) is
      // transient and must NOT be treated as "the install vanished": that
      // was closing the VNC overlay and flipping the button back to
      // "Install" on a single missed poll, while the session (and the
      // install itself) was still very much there server-side.
      const status = (err as { response?: { status?: number } })?.response
        ?.status;
      if (status === 404) {
        session.value = null;
      } else {
        // Keep the stale-but-correct session and just try again next tick
        // instead of stopping the poll loop outright.
        schedulePoll();
        return;
      }
    }
    if (session.value && ACTIVE_STATES.includes(session.value.state)) {
      schedulePoll();
    }
  }

  /** Call once when the button mounts, to resume polling an install already
   *  in flight (e.g. the user navigated away and came back). */
  async function checkExisting() {
    const rom = getRom();
    if (!rom || !canInstall.value) return;
    checking.value = true;
    try {
      await refreshSession();
    } finally {
      checking.value = false;
    }
  }

  /** Call once when the button mounts (Windows ROMs only - see GameActions),
   *  to decide whether "Install" is even offered. One cheap Redis lookup per
   *  page view, not polled continuously. */
  async function checkWorkerAvailable() {
    if (!canInstall.value) return;
    try {
      const { data } = await installApi.getInstallWorkerStatus();
      workerAvailable.value = data.available;
    } catch {
      workerAvailable.value = false;
    }
  }

  async function startWithPath(
    installerPath?: string,
    protonBuild?: string,
    sourcePath?: string,
  ) {
    const rom = getRom();
    if (!rom) return;
    starting.value = true;
    try {
      const { data } = await withWorkerStartupRetry(
        () =>
          installApi.startInstall({
            romId: rom.id,
            installerPath,
            sourcePath,
            protonBuild,
            autoMode: pendingAutoMode.value,
          }),
        {
          onWaiting: (w) => (waitingForWorker.value = w),
          shouldStop: () => !alive.value,
        },
      );
      session.value = data;
      if (ACTIVE_STATES.includes(data.state)) schedulePoll();
    } catch (err) {
      snackbar.error(
        t("rom.install-snackbar-start-failed", { detail: errorDetail(err) }),
        { icon: "mdi-alert-circle-outline" },
      );
    } finally {
      starting.value = false;
    }
  }

  /** Fetch installer candidates without deciding anything - populates
   *  `candidates`/`streamCopy` for the Install page's file-select combo. */
  async function checkCandidates() {
    const rom = getRom();
    if (!rom || !canInstall.value) return;
    try {
      const { data } = await installApi.getInstallCandidates(rom.id);
      candidates.value = data.candidates;
      streamCopy.value = data.stream_copy;
    } catch {
      // Best-effort: the sidebar combo just stays empty.
    }
  }

  /** Executables inside an archive/disc image, read from its listing (the
   *  server extracts nothing until the install actually starts). */
  async function fetchSourceCandidates(sourcePath: string | null) {
    const rom = getRom();
    sourceCandidates.value = [];
    if (!rom || !canInstall.value || !sourcePath) return;
    loadingSourceCandidates.value = true;
    try {
      const { data } = await installApi.getInstallCandidates(
        rom.id,
        sourcePath,
      );
      sourceCandidates.value = data.candidates;
    } catch {
      // Leave the list empty; the server still picks one after unpacking.
    } finally {
      loadingSourceCandidates.value = false;
    }
  }

  /** Proton builds this server knows about, for the version-picker combo.
   *  One cheap lookup per page view, not polled continuously. */
  async function fetchProtonBuilds() {
    if (!canInstall.value) return;
    try {
      const { data } = await installApi.getProtonBuilds();
      protonBuilds.value = data.builds;
    } catch {
      protonBuilds.value = [];
    }
  }

  async function pollProtonDownload(buildId: string) {
    if (!canInstall.value) return;
    try {
      const { data } = await installApi.getProtonDownloadProgress(buildId);
      // Resolve a display label for the build.
      const build = protonBuilds.value.find((b) => b.id === buildId);
      protonDownloadLabel.value = build?.label ?? buildId;

      if (data.extracting) {
        // Tarball downloaded, extraction in progress — show "Installing…".
        protonExtracting.value = true;
        protonDownloadProgress.value = null;
      } else if (data.progress === null) {
        // Download complete and not extracting — build is ready.
        protonExtracting.value = false;
        protonDownloadProgress.value = null;
        fetchProtonBuilds();
      } else {
        protonExtracting.value = false;
        protonDownloadProgress.value = data.progress;
      }
    } catch {
      // Worker might not have started the download yet — leave the last
      // known state and try again on the next session poll.
    }
  }

  /** Actually calls the cancel endpoint and updates local state - shared by
   *  both branches of cancelInstall() below so the API call, session
   *  update, and snackbar only exist in one place. */
  async function doCancel(rom: SimpleRom, clearCache: boolean) {
    cancelling.value = true;
    try {
      const { data } = await installApi.cancelInstall(rom.id, { clearCache });
      session.value = data;
      stopPolling();
      snackbar.success(t("rom.install-snackbar-aborted"), {
        icon: "mdi-check-bold",
      });
    } catch (err) {
      snackbar.error(
        t("rom.install-snackbar-abort-failed", { detail: errorDetail(err) }),
        { icon: "mdi-alert-circle-outline" },
      );
    } finally {
      cancelling.value = false;
    }
  }

  /** Abort a running install (any active state, not just once the VNC
   *  bridge is up). Two steps, same shape as confirmClearIfInstalled: an
   *  install can already have real, useful bytes on disk by the time
   *  someone aborts it, so stopping it must not automatically imply
   *  throwing that away too - the light first prompt asks what to do with
   *  it; the destructive typed-DELETE one only shows up if they choose to
   *  clear it. */
  async function cancelInstall() {
    const rom = getRom();
    if (!rom) return;

    const wantsToKeep = await confirm({
      title: t("rom.install-confirm-abort-choice-title"),
      body: t("rom.install-confirm-abort-choice-body"),
      confirmText: t("rom.install-keep-cache"),
      cancelText: t("rom.install-clear-cache"),
      tone: "danger",
      dangerSide: "cancel",
    });
    if (wantsToKeep) {
      await doCancel(rom, false);
      return;
    }

    const ok = await confirm({
      title: t("rom.install-confirm-abort-title"),
      body: t("rom.install-confirm-abort-body"),
      confirmText: t("rom.install-abort"),
      tone: "danger",
      requireTyped: "DELETE",
    });
    if (!ok) return;
    await doCancel(rom, true);
  }

  /** Offers to clear whatever cache already exists for this ROM right
   *  before a fresh install starts - "Install" is the only button now (no
   *  separate "Reinstall"), so this is where that choice actually
   *  happens, once. A no-op when there's nothing to ask about
   *  (`hasCache` false). Always resolves (never throws) and the caller
   *  proceeds to install either way once this returns - clearing is
   *  optional, not a gate: a fresh attempt starts whether the user clears
   *  the old cache or keeps it, only the old cache's disk usage is at
   *  stake either way.
   *
   *  Two steps, not one: some installers are genuinely meant to be run more
   *  than once against the same install - a patch on top of the base game,
   *  for example - so pressing Install again must not immediately shove a
   *  typed-DELETE confirmation in front of the user just to keep going.
   *  The light first prompt asks what they actually want; the destructive
   *  one only ever shows up if they explicitly chose to clear. */
  async function confirmClearIfInstalled(): Promise<void> {
    const rom = getRom();
    if (!rom || !hasCache.value) return;

    // "Keep existing files" is the default, safe action - it sits in the
    // confirm slot (primary position, plain color). "Clear install cache"
    // is the risky one, so it's the red cancel-slot button instead of the
    // usual primary-position action - see ConfirmDialog's own dangerSide.
    const wantsToKeep = await confirm({
      title: t("rom.install-confirm-reinstall-title"),
      body: t("rom.install-confirm-reinstall-body"),
      confirmText: t("rom.install-keep-cache"),
      cancelText: t("rom.install-clear-cache"),
      tone: "danger",
      dangerSide: "cancel",
    });
    if (wantsToKeep) return;

    const ok = await confirm({
      title: t("rom.install-confirm-clear-title"),
      body: t("rom.install-confirm-clear-body"),
      confirmText: t("rom.install-clear-cache"),
      tone: "danger",
      requireTyped: "DELETE",
    });
    if (!ok) return;
    try {
      await installApi.clearInstallCache(rom.id);
      session.value = null;
    } catch (err) {
      snackbar.error(
        t("rom.install-snackbar-clear-failed", { detail: errorDetail(err) }),
        { icon: "mdi-alert-circle-outline" },
      );
    }
  }

  /** Standalone "Clear install cache" for the Install page's own settings
   *  panel - unlike confirmClearIfInstalled (a silent pre-step folded into
   *  starting a fresh install), this is a self-contained action a user picks
   *  on its own, so it needs its own loading state and success feedback.
   *  Mirrors FilesTab's own dedicated clear-cache button (same confirm
   *  wording/typed-DELETE friction, same endpoint) since it's the same
   *  destructive action either way. */
  async function clearCache(): Promise<void> {
    const rom = getRom();
    if (!rom || !hasCache.value) return;
    const ok = await confirm({
      title: t("rom.install-confirm-clear-title"),
      body: t("rom.install-confirm-clear-body"),
      confirmText: t("rom.install-clear-cache"),
      tone: "danger",
      requireTyped: "DELETE",
    });
    if (!ok) return;

    clearingCache.value = true;
    try {
      await installApi.clearInstallCache(rom.id);
      session.value = null;
      snackbar.success(t("rom.install-snackbar-cache-cleared"), {
        icon: "mdi-check-bold",
      });
    } catch (err) {
      snackbar.error(
        t("rom.install-snackbar-clear-failed", { detail: errorDetail(err) }),
        { icon: "mdi-alert-circle-outline" },
      );
    } finally {
      clearingCache.value = false;
    }
  }

  onScopeDispose(() => {
    stopPolling();
  });

  return {
    canInstall,
    workerAvailable,
    session,
    candidates,
    sourceCandidates,
    loadingSourceCandidates,
    protonBuilds,
    streamCopy,
    checking,
    starting,
    cancelling,
    clearingCache,
    state,
    isRunning,
    isActive,
    awaitingInstallerPick,
    vncUrl,
    hasCache,
    phase,
    phaseDetail,
    autoMode,
    autoStatus,
    autoDetail,
    setAutoMode,
    protonDownloadProgress,
    protonDownloadLabel,
    protonExtracting,
    waitingForWorker,
    checkExisting,
    checkWorkerAvailable,
    checkCandidates,
    fetchProtonBuilds,
    fetchSourceCandidates,
    startWithPath,
    cancelInstall,
    confirmClearIfInstalled,
    clearCache,
  };
}

export type InstallSession = ReturnType<typeof useInstallSession>;

/** Navigate to the Install page and, in parallel (not sequentially), kick
 *  off the actual install request - so the sandbox/VNC startup (the slow
 *  part) begins the instant the click happens, not after the page has
 *  finished mounting. Deliberately a plain function, not part of
 *  useInstallSession's returned object: the caller (e.g. GameActions) is
 *  about to unmount as the route changes, and this must keep running after
 *  that. The Install page's own useInstallSession instance picks up the
 *  resulting session via its normal checkExisting() polling.
 *
 *  Deliberately just one call with no installer_path: the server resolves
 *  everything itself now - already installed, an unambiguous auto-pick, or
 *  falling back to AWAITING_INSTALLER for a human to finish on the Install
 *  page (see start_install_session's own docstring) - so every client gets
 *  identical behavior for free instead of re-fetching candidates and
 *  picking one here too. */
export async function startInstallAndNavigate(
  rom: SimpleRom,
  router: Router,
): Promise<void> {
  void router.push({ name: ROUTES.INSTALL, params: { rom: rom.id } });
  try {
    await withWorkerStartupRetry(() =>
      installApi.startInstall({ romId: rom.id }),
    );
  } catch {
    // Best-effort: the Install page's own checkExisting()/checkCandidates()
    // still give the user a way to see what happened and retry.
  }
}
