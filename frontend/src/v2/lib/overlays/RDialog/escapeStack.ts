// Shared Esc-key stack.
//
// Every escapable v2 overlay (RDialog, RMenu, RDrawer, plus ad-hoc
// panels like the grid-view focus inside MatchRomBodyGrid) pushes
// itself here while open. A single window capture-phase listener
// consults the top of the stack so Esc always closes the most recent
// context first — outer surfaces stay open until inner ones are
// dismissed.
//
// Per-instance `@keydown` on the panel only fires when the event
// happens to bubble to it — which fails whenever a child stops
// propagation, or whenever focus lives outside the panel (a teleported
// listbox, the body itself). A single capture-phase listener on
// `window` sidesteps both.
//
// The stack also doubles as the "is any v2 overlay currently open?"
// registry — `useGamepad`'s B/back action calls `hasOpenEscapable()`
// to decide between "close the top overlay" and "router.back()", so
// gamepad dismiss and Esc share the same source of truth.
//
// Pushing also notifies `onEscapableOpen` subscribers, so surfaces that
// paint above every overlay (RTooltip) can dismiss themselves.

export interface EscapableEntry {
  close: () => void;
  /** When true, this entry stays at the top of the stack but Esc
   *  becomes a no-op for it. Outer entries do not get a chance to
   *  respond either — a persistent layer effectively swallows Esc. */
  persistent: boolean;
  /** The surface this entry paints, for overlays that own one. Lets
   *  `isUnderOpenEscapable` tell content inside the overlay apart from
   *  content the overlay covers. */
  panel?: () => HTMLElement | null;
}

const stack: EscapableEntry[] = [];
const openListeners = new Set<() => void>();

function onWindowKeyDown(evt: KeyboardEvent) {
  if (evt.key !== "Escape") return;
  const top = stack[stack.length - 1];
  if (!top || top.persistent) return;
  evt.stopPropagation();
  top.close();
}

function attachListener() {
  if (stack.length === 1 && typeof window !== "undefined") {
    window.addEventListener("keydown", onWindowKeyDown, true);
  }
}
function detachListener() {
  if (stack.length === 0 && typeof window !== "undefined") {
    window.removeEventListener("keydown", onWindowKeyDown, true);
  }
}

export function pushEscapable(entry: EscapableEntry): void {
  stack.push(entry);
  attachListener();
  for (const listener of [...openListeners]) listener();
}

export function popEscapable(entry: EscapableEntry): void {
  const idx = stack.indexOf(entry);
  if (idx !== -1) {
    stack.splice(idx, 1);
    detachListener();
  }
}

/** Subscribe to "an overlay just opened". Returns an unsubscribe function. */
export function onEscapableOpen(listener: () => void): () => void {
  openListeners.add(listener);
  return () => openListeners.delete(listener);
}

/** True when `el` is covered by the topmost overlay rather than living
 *  inside it. Entries that declare no panel have no opinion, so nothing
 *  counts as covered while one of those is on top. */
export function isUnderOpenEscapable(el: Node | null): boolean {
  const panel = stack[stack.length - 1]?.panel?.();
  if (!panel) return false;
  return !el || !panel.contains(el);
}

/** True when at least one non-persistent escapable overlay is open.
 *  Persistent layers still count as "open" — they block back-style
 *  dismiss the same way Esc is a no-op for them, so the user gets
 *  consistent behaviour across both keys. */
export function hasOpenEscapable(): boolean {
  return stack.length > 0;
}

/** Close the topmost escapable overlay. No-op if the stack is empty or
 *  if the top entry is persistent. Mirrors what Esc does. */
export function closeTopEscapable(): void {
  const top = stack[stack.length - 1];
  if (!top || top.persistent) return;
  top.close();
}

/** Close every open overlay, innermost first. Used on route changes (see
 *  `useOverlayRouteDismiss`), where `persistent` does not apply: it
 *  guards against dismissing a surface by accident, but the page that
 *  surface belonged to is already gone. Iterates over a snapshot since
 *  each `close()` removes its own entry (asynchronously, via the owner's
 *  `modelValue` watcher). */
export function closeAllEscapables(): void {
  for (const entry of [...stack].reverse()) entry.close();
}
