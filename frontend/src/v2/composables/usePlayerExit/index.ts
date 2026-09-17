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
  /**
   * Work the departing document still owes, awaited before it is replaced.
   * A replace aborts the navigation, so the leave guards of the components
   * below never run and whatever they would have flushed belongs here.
   */
  settle: () => Promise<void> | void = () => undefined,
): {
  /** True once an exit is replacing the document, so an unload prompt can stand down. */
  departing: Ref<boolean>;
  /**
   * Go to `path` in place of the player, by a full navigation when the document
   * is bound. The player is replaced either way, so Back never re-enters the
   * view it just left and relaunches the game.
   */
  leave: (path: string) => void;
  /** `onBeforeRouteLeave` guard: lets a departure through unless bound. */
  guard: (to: Pick<RouteLocationNormalized, "fullPath">) => Promise<boolean>;
} {
  const router = useRouter();
  const departing = ref(false);

  function documentBound(): boolean {
    return window.crossOriginIsolated || runtimeBound();
  }

  async function replaceDocument(path: string): Promise<void> {
    departing.value = true;
    try {
      await settle();
    } catch (error) {
      // The document goes either way; stranding the user in the player is worse.
      console.error("Player exit settle failed", error);
    }
    window.location.replace(path);
  }

  function leave(path: string): void {
    if (documentBound()) void replaceDocument(path);
    else void router.replace(path);
  }

  async function guard(
    to: Pick<RouteLocationNormalized, "fullPath">,
  ): Promise<boolean> {
    if (!documentBound()) return true;
    await replaceDocument(to.fullPath);
    return false;
  }

  return { departing, leave, guard };
}
