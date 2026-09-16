// usePlayerExit: how a player view hands the tab back to the app.
//
// Two things can bind a player to its document. A player URL opened directly
// carries the COOP/COEP headers nginx attaches to it, and the resulting
// cross-origin isolation outlives every SPA navigation after it, blocking the
// third-party images the app embeds elsewhere (provider covers in Match ROM).
// And a runtime that declares globals when injected (EmulatorJS) cannot be
// injected a second time. Either way the exit is a full navigation, so the
// app resumes in a fresh document; otherwise it is an SPA navigation.
import { useRouter, type RouteLocationNormalized } from "vue-router";

export function usePlayerExit(
  /** True once the view injected a runtime the document cannot take twice. */
  runtimeBound: () => boolean = () => false,
): {
  /** Whether leaving has to replace the document. */
  documentBound: () => boolean;
  /** Go to `path`, by a full navigation when the document is bound. */
  leave: (path: string) => void;
  /** `onBeforeRouteLeave` guard: lets a departure through unless bound. */
  guard: (to: Pick<RouteLocationNormalized, "fullPath">) => boolean;
} {
  const router = useRouter();
  // Set by leave() so the guard lets its own push through.
  let leaving = false;

  function documentBound(): boolean {
    return window.crossOriginIsolated || runtimeBound();
  }

  function leave(path: string): void {
    if (documentBound()) {
      window.location.replace(path);
      return;
    }
    leaving = true;
    void router.push(path).finally(() => {
      leaving = false;
    });
  }

  function guard(to: Pick<RouteLocationNormalized, "fullPath">): boolean {
    if (leaving || !documentBound()) return true;
    window.location.replace(to.fullPath);
    return false;
  }

  return { documentBound, leave, guard };
}
