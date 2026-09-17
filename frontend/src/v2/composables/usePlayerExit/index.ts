// usePlayerExit: how a player view hands the tab back to the app.
//
// Two things bind a player to its document: cross-origin isolation, which
// outlives every SPA navigation after it and blocks the third-party images the
// app embeds elsewhere, and a runtime that cannot be injected twice. Either
// leaves the app a fresh document to resume in; otherwise leaving is an SPA
// navigation.
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
