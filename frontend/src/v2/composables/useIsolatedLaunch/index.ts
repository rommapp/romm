// useIsolatedLaunch: reloading a player view into a cross-origin isolated
// document.
//
// A runtime that needs SharedArrayBuffer only gets it in a cross-origin
// isolated document, and a view reached by SPA navigation is not one. Nginx
// attaches the COOP/COEP headers to the player URLs, so reloading the view is
// what isolates it. What the user had set up crosses the reload as an intent
// kept per tab, and the view boots from it on arrival.
//
// Usage, in a player whose runtime (or one of its cores) needs it:
//   const { intent, relaunching, relaunch } =
//     useIsolatedLaunch<MyIntent>("myplayer", romId, isMyIntent);
//   on Play:  if (!hasSharedArrayBuffer()) {
//               if (!relaunch(currentIntent())) reportInsecureContext();
//               return;
//             }
//   on mount: if (intent) { apply(intent); boot(); }
// Pair it with usePlayerExit, which drops the isolation again on the way out.
import { ref, type Ref } from "vue";

export function hasSharedArrayBuffer(): boolean {
  return typeof window.SharedArrayBuffer === "function";
}

export function useIsolatedLaunch<Intent>(
  player: string,
  romId: number,
  isIntent: (value: unknown) => value is Intent,
): {
  /** What the view stored before reloading, or null when it opened normally. */
  intent: Intent | null;
  /** True once a reload is under way, so the Play control stays busy. */
  relaunching: Ref<boolean>;
  /**
   * Keep `intent` and reload into the isolated document. False when this view
   * already came from such a reload: the context cannot be isolated (plain
   * HTTP, or a proxy dropping the headers), so the caller reports it instead.
   */
  relaunch: (intent: Intent) => boolean;
} {
  const key = `player:${romId}:${player}:launch`;
  const intent = takeIntent(key, isIntent);
  const relaunching = ref(false);

  function relaunch(next: Intent): boolean {
    if (intent !== null) return false;
    relaunching.value = true;
    sessionStorage.setItem(key, JSON.stringify(next));
    window.location.reload();
    return true;
  }

  return { intent, relaunching, relaunch };
}

/** The intent under `key`, cleared on read so it boots only once. */
function takeIntent<Intent>(
  key: string,
  isIntent: (value: unknown) => value is Intent,
): Intent | null {
  const raw = sessionStorage.getItem(key);
  if (raw === null) return null;
  sessionStorage.removeItem(key);
  try {
    const parsed: unknown = JSON.parse(raw);
    return isIntent(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
