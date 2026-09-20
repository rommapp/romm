// useGallerySelectionInput — shared input plumbing that turns
// raw card/row clicks into selection-store mutations. Used by
// GameCard and GameListRow so the click semantics stay aligned
// between grid and list mode.
//
// Selection semantics:
//   - When the store is already `enabled` (selection mode), a plain
//     click toggles the card. The default action (navigation) is
//     suppressed.
//   - When the store is *not* enabled, a plain click falls through
//     to the default (navigate to ROM details). Modifier-click still
//     enters selection mode: Shift toggles + sets anchor, Ctrl/Cmd
//     toggles alone.
//   - Shift-click against an existing anchor selects the range
//     [anchor, target] inclusive — direction-aware (extends the
//     selection if the target was unselected, shrinks if it was
//     selected). Sparse positions skip silently — ROMs not loaded
//     yet are not toggled.
//   - On touch, a 500ms long-press enters selection mode without a
//     modifier key. The subsequent `click` event is swallowed so the
//     touch press doesn't double-fire as navigation.
//
// The composable returns three handlers; callers wire them to their
// component's native event slots and short-circuit the default
// behaviour when `handleActivate` returns `true`. Owning the long-
// press state inside the composable keeps the GameCard / GameListRow
// markup free of pointer-tracking boilerplate.
import type { SimpleRom } from "@/stores/roms";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";

const LONG_PRESS_MS = 500;
const LONG_PRESS_MOVE_TOLERANCE_PX = 8;
/** How close to the scroller's edge the finger has to get before a paint
 *  drag starts pulling the list along, and how fast it pulls at the very
 *  edge. Below that band the drag is a plain paint. */
const EDGE_BAND_PX = 72;
const EDGE_MAX_SPEED_PX = 14;

interface LongPressState {
  romId: number;
  position: number;
  startX: number;
  startY: number;
  timer: ReturnType<typeof setTimeout> | null;
  /** Set to true the moment the long-press fires. The subsequent
   * `click` (the browser still synthesises one from the touch
   * sequence) checks this flag and bails out. */
  consumed: boolean;
}

let longPress: LongPressState | null = null;
/** Positions already painted by the current drag, so sliding back over one
 *  doesn't flip it off again. Null while no drag is painting. */
let painted: Set<number> | null = null;
/** True between a tracked touch going down and coming back up. The long-press
 *  state outlives that, waiting for the click it has to swallow. */
let pressActive = false;
/** Where the finger is, for the auto-scroll to keep painting from. */
let paintPoint: { x: number; y: number } | null = null;
let paintScroller: HTMLElement | null = null;
let edgeFrame: number | null = null;

function stopEdgeScroll() {
  if (edgeFrame !== null) cancelAnimationFrame(edgeFrame);
  edgeFrame = null;
  paintPoint = null;
  paintScroller = null;
}

function resetLongPress() {
  if (longPress?.timer) clearTimeout(longPress.timer);
  longPress = null;
  painted = null;
  stopEdgeScroll();
}

/** Nearest ancestor that actually scrolls, which is what the drag pulls. */
function scrollableAncestor(el: Element | null): HTMLElement | null {
  for (let node = el; node instanceof HTMLElement; node = node.parentElement) {
    const overflowY = getComputedStyle(node).overflowY;
    if (
      (overflowY === "auto" || overflowY === "scroll") &&
      node.scrollHeight > node.clientHeight
    ) {
      return node;
    }
  }
  return null;
}

/** Px to scroll this frame: nothing until the finger enters the edge band,
 *  then proportional to how far into it the finger has gone. Exported for
 *  its own test; the drag itself reads it through `runEdgeScroll`. */
export function edgeSpeed(y: number, top: number, bottom: number): number {
  if (y < top + EDGE_BAND_PX) {
    return (
      -EDGE_MAX_SPEED_PX * Math.min(1, (top + EDGE_BAND_PX - y) / EDGE_BAND_PX)
    );
  }
  if (y > bottom - EDGE_BAND_PX) {
    return (
      EDGE_MAX_SPEED_PX *
      Math.min(1, (y - (bottom - EDGE_BAND_PX)) / EDGE_BAND_PX)
    );
  }
  return 0;
}

export function useGallerySelectionInput() {
  const selection = storeGallerySelection();
  const galleryRoms = storeGalleryRoms();

  /** Handle a card/row activation (click). Returns `true` if the
   * event was consumed by the selection logic — caller should skip
   * navigation. Returns `false` to fall through to default. */
  function handleActivate(
    rom: SimpleRom,
    position: number,
    event: MouseEvent | KeyboardEvent,
  ): boolean {
    // Long-press has already mutated the store and now wants to
    // suppress the synthetic click that follows.
    if (longPress?.consumed) {
      event.preventDefault();
      event.stopPropagation();
      resetLongPress();
      return true;
    }

    const mouse = event as MouseEvent;
    const isShift = mouse.shiftKey === true;
    const isMod = mouse.ctrlKey === true || mouse.metaKey === true;

    if (selection.enabled || isShift || isMod) {
      event.preventDefault();
      event.stopPropagation();
      if (isShift) {
        selection.toggleRange(position, (p) => galleryRoms.getRomAt(p));
      } else {
        selection.toggle(rom, position);
      }
      return true;
    }

    return false;
  }

  /** Begin tracking a touch for long-press. Mouse events skip this —
   * desktop users have keyboard modifiers; long-press on mouse would
   * fight click-and-drag selection. */
  function handlePointerDown(
    rom: SimpleRom,
    position: number,
    event: PointerEvent,
  ) {
    if (event.pointerType !== "touch") return;
    if (event.isPrimary === false) return;
    // A press that lands on a control belongs to that control. The row and
    // the card are an `<a>`, so neither matches this and both still track.
    const target = event.target;
    if (
      target instanceof Element &&
      target.closest("button, input, select, textarea, [role='menuitem']")
    ) {
      return;
    }

    resetLongPress();
    pressActive = true;
    longPress = {
      romId: rom.id,
      position,
      startX: event.clientX,
      startY: event.clientY,
      timer: null,
      consumed: false,
    };

    const state = longPress;
    state.timer = setTimeout(() => {
      // Re-check the global state — if the user lifted or moved
      // beyond tolerance before the timer fired, `longPress` will
      // have been reset and this branch becomes a no-op.
      if (longPress !== state) return;
      state.consumed = true;
      state.timer = null;
      selection.toggle(rom, position);
      // Whatever the press selected is the drag's first row.
      painted = new Set([position]);
    }, LONG_PRESS_MS);
  }

  /** Select the row under the finger, if it is one we haven't painted. */
  function paintAt(clientX: number, clientY: number) {
    if (!painted) return;
    const host = document
      .elementFromPoint(clientX, clientY)
      ?.closest<HTMLElement>("[data-rom-position]");
    if (!host) return;
    const position = Number(host.dataset.romPosition);
    paintScroller ??= scrollableAncestor(host);
    if (!Number.isInteger(position) || painted.has(position)) return;
    const rom = galleryRoms.getRomAt(position);
    if (!rom) return;
    painted.add(position);
    selection.selectMany([rom]);
  }

  /** While the finger sits in the edge band, pull the list past it and keep
   *  painting whatever arrives under it, so a drag can run past one screen. */
  function runEdgeScroll() {
    edgeFrame = null;
    const scroller = paintScroller;
    const point = paintPoint;
    if (!painted || !scroller || !point) return;
    const { top, bottom } = scroller.getBoundingClientRect();
    const speed = edgeSpeed(point.y, top, bottom);
    if (speed !== 0) {
      const before = scroller.scrollTop;
      scroller.scrollTop += speed;
      if (scroller.scrollTop !== before) paintAt(point.x, point.y);
    }
    edgeFrame = requestAnimationFrame(runEdgeScroll);
  }

  /** True while a long press has turned into a drag that paints rows. */
  function isPainting(): boolean {
    return painted !== null;
  }

  /** Suppress the native callout the browser offers on a long press, which
   *  would otherwise cover the selection the press just made. Only a live
   *  touch counts, so a right-click still opens the browser's menu. */
  function handleContextMenu(event: Event) {
    if (pressActive) event.preventDefault();
  }

  function handlePointerMove(event: PointerEvent) {
    if (!longPress) return;
    // Past the long press, the drag selects every row it crosses. Touch
    // events stay with the element that got the press, so the row under the
    // finger is looked up by coordinates.
    if (longPress.consumed) {
      paintPoint = { x: event.clientX, y: event.clientY };
      paintAt(event.clientX, event.clientY);
      if (edgeFrame === null) edgeFrame = requestAnimationFrame(runEdgeScroll);
      return;
    }
    const dx = Math.abs(event.clientX - longPress.startX);
    const dy = Math.abs(event.clientY - longPress.startY);
    if (
      dx > LONG_PRESS_MOVE_TOLERANCE_PX ||
      dy > LONG_PRESS_MOVE_TOLERANCE_PX
    ) {
      resetLongPress();
    }
  }

  function handlePointerEnd() {
    pressActive = false;
    stopEdgeScroll();
    // If the timer hasn't fired yet, the press was a normal tap —
    // cancel so the click event passes through unchanged. If it did
    // fire (`consumed: true`), keep the state so the synthetic click
    // can detect and swallow itself.
    if (!longPress) return;
    if (!longPress.consumed) resetLongPress();
  }

  return {
    handleActivate,
    handleContextMenu,
    isPainting,
    handlePointerDown,
    handlePointerMove,
    handlePointerEnd,
  };
}
