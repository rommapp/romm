// The only module that touches `window.rommNative`, the bridge the RomM
// desktop shell injects into the page it loads (see `@/types/rommNative`).
//
// The shell loads whatever frontend its server serves, so a shell older than
// this server may be missing methods declared here: every call feature-detects
// its own and absence reads as "no native play".
import type {
  LaunchRequest,
  LaunchResult,
  LaunchState,
  PlatformSupport,
  PlatformSupportQuery,
  RommNativeBridge,
} from "@/types/rommNative";

function bridge(): RommNativeBridge | undefined {
  return window.rommNative;
}

function hasMethod(name: keyof RommNativeBridge): boolean {
  return typeof bridge()?.[name] === "function";
}

/** Whether the page is running inside the desktop shell at all. */
export function isNativeShell(): boolean {
  return hasMethod("launch");
}

/** For display and support only. Behaviour is gated on
 *  `hasNativeCapability`, never on a parsed version. */
export function nativeShellVersion(): string | null {
  return bridge()?.shellVersion ?? null;
}

/** Whether the shell declares a behaviour that method presence cannot express.
 *  A shell predating the capability list reports none. */
export function hasNativeCapability(name: string): boolean {
  const capabilities = bridge()?.capabilities;
  return Array.isArray(capabilities) && capabilities.includes(name);
}

/** Ask which of these platforms the shell can launch, keyed by platform slug.
 *  Never throws: a probe that fails means no native play, which is what the
 *  empty answer says. */
export async function fetchPlatformSupport(
  queries: PlatformSupportQuery[],
): Promise<Record<string, PlatformSupport>> {
  const native = bridge();
  if (!native || queries.length === 0) return {};

  try {
    if (typeof native.getPlatformSupportAll === "function") {
      return await native.getPlatformSupportAll(queries);
    }
    if (typeof native.getPlatformSupport !== "function") return {};
    const answers = await Promise.all(
      queries.map(async (query) => {
        try {
          return [query.platformSlug, await native.getPlatformSupport(query)];
        } catch {
          // One unanswerable platform should not lose the rest of the library.
          return null;
        }
      }),
    );
    return Object.fromEntries(
      answers.filter((entry): entry is [string, PlatformSupport] => !!entry),
    );
  } catch (error) {
    console.error("[native] Could not probe platform support:", error);
    return {};
  }
}

/** Start a ROM in a locally installed emulator. The rejection carries only a
 *  message, because an error code does not survive the shell's IPC boundary;
 *  the code is on the `failed` launch state the shell emits alongside it. */
export function launchNative(request: LaunchRequest): Promise<LaunchResult> {
  const native = bridge();
  if (typeof native?.launch !== "function") {
    return Promise.reject(new Error("The desktop shell cannot launch games."));
  }
  return native.launch(request);
}

/** Abort a launch that is still downloading. A running emulator is left alone
 *  by the shell, so this is only meaningful before the game starts. */
export async function cancelNative(romId: number): Promise<void> {
  const native = bridge();
  if (typeof native?.cancel !== "function") return;
  try {
    await native.cancel(romId);
  } catch (error) {
    console.error("[native] Could not cancel the launch:", error);
  }
}

/** Subscribe to launch progress. Returns an unsubscribe function, which is a
 *  no-op when there is no bridge to unsubscribe from. */
export function onNativeLaunchState(
  listener: (state: LaunchState) => void,
): () => void {
  const native = bridge();
  if (typeof native?.onLaunchState !== "function") return () => {};
  try {
    return native.onLaunchState(listener);
  } catch (error) {
    console.error("[native] Could not subscribe to launch state:", error);
    return () => {};
  }
}

/** Whether this shell has settings to open, so an entry point for them can be
 *  hidden on one that does not. */
export function canOpenNativeSettings(): boolean {
  return hasMethod("openSettings");
}

export async function openNativeSettings(): Promise<void> {
  const native = bridge();
  if (typeof native?.openSettings !== "function") return;
  try {
    await native.openSettings();
  } catch (error) {
    console.error("[native] Could not open the shell settings:", error);
  }
}
