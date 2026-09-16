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

/** For display and support only. Behaviour is gated on the presence of the
 *  method being called, never on a parsed version. */
export function nativeShellVersion(): string | null {
  return bridge()?.shellVersion ?? null;
}

/** The shell rejects a bulk query larger than this, whole, so a library with
 *  more platforms than it has to be asked in batches. Vendored from the
 *  shell's `MAX_PLATFORM_QUERIES`, like the types above. */
const MAX_PLATFORM_QUERIES = 512;

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
      const bulk = native.getPlatformSupportAll.bind(native);
      const answers: Record<string, PlatformSupport> = {};
      for (let at = 0; at < queries.length; at += MAX_PLATFORM_QUERIES) {
        const batch = queries.slice(at, at + MAX_PLATFORM_QUERIES);
        try {
          Object.assign(answers, await bulk(batch));
        } catch (error) {
          // One refused batch is not the rest of the library: a whole-batch
          // rejection here would otherwise turn native play off everywhere.
          console.error("[native] Could not probe a batch:", error);
        }
      }
      return answers;
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

/** Start a ROM in a locally installed emulator. An older shell drops the error
 *  code crossing its IPC boundary, so the code is read off the `failed` launch
 *  state emitted alongside the rejection. */
export function launchNative(request: LaunchRequest): Promise<LaunchResult> {
  const native = bridge();
  if (typeof native?.launch !== "function") {
    return Promise.reject(new Error("The desktop shell cannot launch games."));
  }
  return native.launch(request);
}

/**
 * Abort a launch that is still downloading. A running emulator is left alone
 * by the shell, so this is only meaningful before the game starts.
 *
 * Answers whether the shell took the cancel. A refusal leaves the launch
 * running, so a caller that reported it as cancelled anyway would be claiming
 * something untrue and would swallow the failure that follows.
 */
export async function cancelNative(romId: number): Promise<boolean> {
  const native = bridge();
  if (typeof native?.cancel !== "function") return false;
  try {
    await native.cancel(romId);
    return true;
  } catch (error) {
    console.error("[native] Could not cancel the launch:", error);
    return false;
  }
}

/** The message out of anything the bridge throws. A shell carrying
 *  rommapp/romm-desktop#11 rejects with a plain LaunchFailure rather than an
 *  Error, which String() renders as "[object Object]". */
export function nativeErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error) {
    const { message } = error as { message: unknown };
    if (typeof message === "string" && message !== "") return message;
  }
  return String(error);
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
