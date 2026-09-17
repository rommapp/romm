// usePlayerExit: how a player view hands the tab back to the app.
//
// Two things can bind a player to its document. A player URL opened directly
// carries the COOP/COEP headers nginx attaches to it, and the resulting
// cross-origin isolation outlives every SPA navigation after it, blocking the
// third-party images the app embeds elsewhere (provider covers in Match ROM).
// And a runtime that declares globals when injected (EmulatorJS) cannot be
// injected a second time. Either way the exit is a full navigation, so the
// app resumes in a fresh document; otherwise it is an SPA navigation.
import { ref, type Ref } from "vue";
import { useRouter, type RouteLocationNormalized } from "vue-router";

export function usePlayerExit(
  /** True once the view injected a runtime the document cannot take twice. */
  runtimeBound: () => boolean = () => false,
): {
  /** True once an exit is replacing the document, so an unload prompt can stand down. */
  departing: Ref<boolean>;
  /** Go to `path`, by a full navigation when the document is bound. */
  leave: (path: string) => void;
  /** `onBeforeRouteLeave` guard: lets a departure through unless bound. */
  guard: (to: Pick<RouteLocationNormalized, "fullPath">) => boolean;
} {
  const router = useRouter();
  const departing = ref(false);

  function documentBound(): boolean {
    return window.crossOriginIsolated || runtimeBound();
  }

  function replaceDocument(path: string): void {
    departing.value = true;
    window.location.replace(path);
  }

  function leave(path: string): void {
    if (documentBound()) replaceDocument(path);
    else void router.push(path);
  }

  function guard(to: Pick<RouteLocationNormalized, "fullPath">): boolean {
    if (!documentBound()) return true;
    replaceDocument(to.fullPath);
    return false;
  }

  return { departing, leave, guard };
}
