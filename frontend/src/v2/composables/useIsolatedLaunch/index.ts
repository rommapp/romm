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
   * Keep `intent` and reload into the isolated document. False when the reload
   * would not help: the context is not secure (the headers alone never expose
   * SharedArrayBuffer), the selection could not be kept, or this view already
   * came from such a reload. The caller reports the context instead.
   */
  relaunch: (intent: Intent) => boolean;
} {
  const key = `player:${romId}:${player}:launch`;
  const intent = takeIntent(key, isIntent);
  const relaunching = ref(false);

  function relaunch(next: Intent): boolean {
    if (intent !== null || !window.isSecureContext) return false;
    if (!keepIntent(key, next)) return false;
    relaunching.value = true;
    window.location.reload();
    return true;
  }

  return { intent, relaunching, relaunch };
}

// Storage access can be denied outright (a strict privacy mode, a blocked
// third-party context), and a player must open and run regardless, so both
// sides treat that as "no intent" rather than throwing through the view.

function keepIntent(key: string, intent: unknown): boolean {
  try {
    sessionStorage.setItem(key, JSON.stringify(intent));
    return true;
  } catch {
    return false;
  }
}

/** The intent under `key`, cleared on read so it boots only once. */
function takeIntent<Intent>(
  key: string,
  isIntent: (value: unknown) => value is Intent,
): Intent | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (raw === null) return null;
    sessionStorage.removeItem(key);
    const parsed: unknown = JSON.parse(raw);
    return isIntent(parsed) ? parsed : null;
  } catch {
    return null;
  }
}
