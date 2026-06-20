// Pure mouse-event helpers shared across input-aware primitives. No
// dependencies — safe to import from `lib` primitives.

/**
 * True when a click on a link should be left to the browser's native
 * "open elsewhere" behaviour — new tab (Ctrl / ⌘), new window (Shift),
 * or download (Alt) — instead of in-app SPA navigation.
 *
 * Why primitives care: RouterLink already bails out of programmatic
 * navigation for these gestures, letting the default `<a>` action through.
 * But any surrounding "close the menu / drawer" logic must bail too —
 * otherwise the (often teleported) `<a>` is unmounted on Vue's microtask
 * flush before the browser performs its default action, swallowing the
 * new tab. Menus gate their close on this; items gate their click emit.
 */
export function opensInNewContext(event: MouseEvent): boolean {
  return event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
}
