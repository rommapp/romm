// useUnloadGuard arms the browser's "leave site?" prompt while a game is
// live, so a reload or tab close can't drop unsaved progress (#4298).
import { useEventListener } from "@vueuse/core";
import { toValue, type MaybeRefOrGetter } from "vue";

export function useUnloadGuard(armed: MaybeRefOrGetter<boolean>): void {
  if (typeof window === "undefined") return;

  useEventListener(window, "beforeunload", (event: BeforeUnloadEvent) => {
    if (!toValue(armed)) return;
    // preventDefault covers the current spec, returnValue the older browsers.
    event.preventDefault();
    event.returnValue = "";
  });
}
