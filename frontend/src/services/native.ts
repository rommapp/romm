// The only module that touches `window.rommNative`, the bridge the desktop shell
// injects. Every call feature-detects its own: a shell serves its own frontend.
import type {
  LaunchRequest,
  LaunchResult,
  LaunchState,
  PlatformSupport,
  PlatformSupportQuery,
  RommNativeBridge,
  ShellCapability,
} from "@/types/rommNative";

function bridge(): RommNativeBridge | undefined {
  return window.rommNative;
}

function hasMethod(name: keyof RommNativeBridge): boolean {
  return typeof bridge()?.[name] === "function";
}

/** Whether this shell advertises a behaviour a method's presence cannot express.
 *  Read from the list, not `shellVersion`, which is for display only. */
export function hasCapability(name: ShellCapability): boolean {
  return bridge()?.capabilities?.includes(name) === true;
}

/** Whether a native launch moves saves to and from the server. A shell without
 *  it leaves them on this disk. */
export function canSyncSaves(): boolean {
  return isNativeShell() && hasCapability("save-sync");
}

/** Whether a native launch honours the page's full-screen choice, which is
 *  otherwise the browser player's alone. */
export function canLaunchFullscreen(): boolean {
  return isNativeShell() && hasCapability("launch-fullscreen");
}

/** Whether a native launch honours the page's disc choice, which is otherwise
 *  the browser player's alone. Sent regardless: a shell drops unknown fields. */
export function canPickDisc(): boolean {
  return isNativeShell() && hasCapability("disc-choice");
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

/** The shell rejects a bulk query larger than this, whole, so a bigger library
 *  is asked in batches. Vendored from the shell's own limit. */
const MAX_PLATFORM_QUERIES = 512;

/** Ask which of these platforms the shell can launch, keyed by platform slug.
 *  Never throws: a failed probe means no native play, which is what it answers. */
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
    // One call per platform here, in the same batches: a full library would
    // otherwise open a renderer-to-main call per platform at once.
    const answers: Record<string, PlatformSupport> = {};
    for (let at = 0; at < queries.length; at += MAX_PLATFORM_QUERIES) {
      const batch = queries.slice(at, at + MAX_PLATFORM_QUERIES);
      const settled = await Promise.all(
        batch.map(async (query) => {
          try {
            return [query.platformSlug, await native.getPlatformSupport(query)];
          } catch {
            // One unanswerable platform should not lose the rest of the library.
            return null;
          }
        }),
      );
      for (const entry of settled) {
        if (entry) answers[entry[0] as string] = entry[1] as PlatformSupport;
      }
    }
    return answers;
  } catch (error) {
    console.error("[native] Could not probe platform support:", error);
    return {};
  }
}

/** Start a ROM in a locally installed emulator. An older shell drops the error
 *  code crossing its IPC boundary, so it is read off the `failed` state. */
export function launchNative(request: LaunchRequest): Promise<LaunchResult> {
  const native = bridge();
  if (typeof native?.launch !== "function") {
    return Promise.reject(new Error("The desktop shell cannot launch games."));
  }
  return native.launch(request);
}

/** Abort a still-downloading launch. Answers whether the request reached the
 *  shell: `cancel` is silent either way, so the outcome comes off the state. */
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

/** The message out of anything the bridge throws, including a rejection that is
 *  a plain object rather than an Error. */
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

/** Ask the shell to show its own settings, answering whether it did, so a caller
 *  can tell a refusal from a press. */
export async function openNativeSettings(): Promise<boolean> {
  const native = bridge();
  if (typeof native?.openSettings !== "function") return false;
  try {
    await native.openSettings();
    return true;
  } catch (error) {
    console.error("[native] Could not open the shell settings:", error);
    return false;
  }
}
