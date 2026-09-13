// useNativeShell — launching a game in a locally installed emulator.
//
// Only does anything when RomM is running inside the desktop shell
// (electron/), which injects `window.rommNative`. In a normal browser every
// flag here is false and the UI simply never offers the action.
//
// Usage:
//   const native = useNativeShell(() => rom.value);
//   native.canLaunch          // ComputedRef<boolean>
//   native.emulatorLabel      // ComputedRef<string | null>
//   await native.launch();
import { computed, type ComputedRef, ref, watchEffect } from "vue";
import { useI18n } from "vue-i18n";
import type { SimpleRom } from "@/stores/roms";
import { getDownloadPath, getSupportedEJSCores } from "@/utils";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import type {
  NativeLaunchErrorCode,
  NativeLaunchState,
  NativePlatformSupport,
  NativeShellBridge,
} from "@/v2/types/nativeShell";

/** Support answers keyed by platform slug, so a gallery of one platform costs
 *  a single probe rather than one per card. */
const supportByPlatform = ref(new Map<string, NativePlatformSupport>());

/** Latest state per ROM, fed by the shell's launch events. */
const launchStates = ref(new Map<number, NativeLaunchState>());

const probing = new Set<string>();
let subscribed = false;

function bridge(): NativeShellBridge | null {
  return typeof window === "undefined" ? null : (window.rommNative ?? null);
}

/** Attach to the shell's launch stream once, on first use. */
function ensureSubscription(shell: NativeShellBridge): void {
  if (subscribed) return;
  subscribed = true;
  shell.onLaunchState((state) => {
    launchStates.value.set(state.romId, state);
  });
}

async function probePlatform(
  shell: NativeShellBridge,
  platformSlug: string,
  cores: string[],
): Promise<void> {
  if (probing.has(platformSlug) || supportByPlatform.value.has(platformSlug)) {
    return;
  }
  probing.add(platformSlug);
  try {
    const support = await shell.getPlatformSupport({ platformSlug, cores });
    supportByPlatform.value.set(platformSlug, support);
  } catch {
    // A shell that cannot answer is treated as unable to launch, which is
    // also what an older shell without this channel looks like.
    supportByPlatform.value.set(platformSlug, {
      supported: false,
      reason: "no-emulator-configured",
    });
  } finally {
    probing.delete(platformSlug);
  }
}

const ERROR_KEYS: Record<NativeLaunchErrorCode, string> = {
  "unsupported-platform": "play.native-error-unsupported-platform",
  "no-emulator-configured": "play.native-error-no-emulator",
  "emulator-not-found": "play.native-error-emulator-missing",
  "download-failed": "play.native-error-download",
  "already-running": "play.native-error-already-running",
  "invalid-request": "play.native-error-generic",
  "launch-failed": "play.native-error-generic",
};

function errorCodeOf(error: unknown): NativeLaunchErrorCode {
  const code = (error as { code?: unknown } | null)?.code;
  return typeof code === "string" && code in ERROR_KEYS
    ? (code as NativeLaunchErrorCode)
    : "launch-failed";
}

export function useNativeShell(
  getRom: () => SimpleRom | null | undefined = () => null,
): {
  isNativeShell: ComputedRef<boolean>;
  canLaunch: ComputedRef<boolean>;
  emulatorLabel: ComputedRef<string | null>;
  launchState: ComputedRef<NativeLaunchState | null>;
  isLaunching: ComputedRef<boolean>;
  launch: () => Promise<void>;
  cancel: () => Promise<void>;
} {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const isNativeShell = computed(() => bridge() !== null);

  /** The libretro cores RomM already knows for this ROM's platform. The shell
   *  is told which cores are candidates and picks one it has installed. */
  const cores = computed(() => {
    const rom = getRom();
    return rom ? getSupportedEJSCores(rom.platform_slug) : [];
  });

  watchEffect(() => {
    const shell = bridge();
    const rom = getRom();
    if (!shell || !rom?.has_file_on_disk) return;
    ensureSubscription(shell);
    void probePlatform(shell, rom.platform_slug, cores.value);
  });

  const support = computed(() => {
    const rom = getRom();
    return rom
      ? (supportByPlatform.value.get(rom.platform_slug) ?? null)
      : null;
  });

  const canLaunch = computed(() => {
    const rom = getRom();
    if (!rom?.has_file_on_disk) return false;
    return support.value?.supported === true;
  });

  const emulatorLabel = computed(() => support.value?.emulator ?? null);

  const launchState = computed(() => {
    const rom = getRom();
    return rom ? (launchStates.value.get(rom.id) ?? null) : null;
  });

  const isLaunching = computed(() => {
    const status = launchState.value?.status;
    return status === "downloading" || status === "running";
  });

  async function launch(): Promise<void> {
    const shell = bridge();
    const rom = getRom();
    if (!shell || !rom || !canLaunch.value || isLaunching.value) return;

    // A large ROM downloads before the emulator starts, so the launch is
    // acknowledged on click rather than when the shell finally resolves.
    snackbar.info(
      t("play.native-launching", { emulator: emulatorLabel.value ?? "" }),
    );

    try {
      await shell.launch({
        romId: rom.id,
        downloadPath: getDownloadPath({ rom }),
        fileName: rom.fs_name,
        platformSlug: rom.platform_slug,
        cores: cores.value,
        name: rom.name ?? rom.fs_name_no_ext,
      });
    } catch (error) {
      snackbar.error(t(ERROR_KEYS[errorCodeOf(error)]));
    }
  }

  /** Abort a download that has not reached the emulator yet. */
  async function cancel(): Promise<void> {
    const shell = bridge();
    const rom = getRom();
    if (!shell || !rom) return;
    await shell.cancel(rom.id);
    launchStates.value.delete(rom.id);
  }

  return {
    isNativeShell,
    canLaunch,
    emulatorLabel,
    launchState,
    isLaunching,
    launch,
    cancel,
  };
}
