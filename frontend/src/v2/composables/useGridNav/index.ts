// useGridNav
//
// 2D arrow-key navigation for a vertical stack of horizontal card rows,
// as used on the Home dashboard (continue playing / recently added /
// favorites / platforms / collections) and anywhere else we compose
// `<CardRow>` stacks.
//
// Mechanics:
//   * Rows are discovered via `rowSelector` (default `.card-row__track`).
//     Any descendant of the root matching that selector is treated as a
//     row. The default matches CardRow's scroll track; consumers like
//     GalleryShell pass their own row class.
//   * Cells are the direct DOM children of each row container.
//   * The focusable target for a cell is the cell itself if it matches a
//     focusable selector, otherwise the first focusable descendant.
//   * ArrowLeft / ArrowRight → prev / next cell in the current row.
//   * ArrowUp / ArrowDown → same column in the prev / next row (clamped).
//   * On autofocus we remember a "preferred column" and restore it when
//     moving up/down through rows of different lengths — common media-UI
//     pattern so row switching doesn't permanently lose horizontal place.
//   * Roving tabindex — the grid is a SINGLE tab stop. Exactly one cell
//     is tabbable at a time; every other card link AND every nested
//     in-card action button (the hidden hover overlay's play / download /
//     favorite / more, natural tab stops even while invisible) drops to
//     tabindex="-1". So Tab enters the grid once and leaves to the next
//     region instead of walking hundreds of stops; Arrow keys move
//     within. Established eagerly on mount and re-synced as virtualised
//     rows mount / unmount, not just after the first arrow / gamepad move.
//   * Card action row — those swept-out overlay buttons are still
//     reachable on a gamepad: X/Y drops focus into the focused card's
//     actions, then D-pad moves between them and B (Escape) returns to
//     the card.
//
// Integration:
//   * Input modality flipping to `"pad"` (gamepad connected / pressed)
//     autofocuses the first cell, so `useGamepad`'s synthetic arrow keys
//     immediately land somewhere useful.
//   * `useGamepad` itself dispatches keydowns — so everything here is
//     plain keyboard code; gamepad users transparently benefit.
//
// For wrapping CSS grids (PlatformsIndex / CollectionsIndex) — where
// there are no per-row DOM containers — use `useWrapGridNav` instead;
// it detects rows spatially from cell rects.
import { onBeforeUnmount, onMounted, watch, type Ref } from "vue";
import { useRoute } from "vue-router";
import { useInputModality } from "@/v2/composables/useInputModality";
import storeFocusRestoration from "@/v2/stores/focusRestoration";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export interface UseGridNavOptions {
  /** Selector that resolves to one DOM element per logical row.
   *  Defaults to `.card-row__track` (CardRow's scroll track). Ignored
   *  when `getRows` is provided. */
  rowSelector?: string;
  /** Returns the row elements. Overrides `rowSelector`. Useful when
   *  the root element itself IS the only row (single-row toolbars
   *  like GameDetails' action ribbon) — pass `() => [rootEl.value!]`. */
  getRows?: () => HTMLElement[];
  /** Returns the cells of a given row. Defaults to the row's direct
   *  children. Pass `(row) => [row]` for list-mode rows where the row
   *  element itself is the single focusable cell, or a custom selector
   *  to skip non-focusable spacers / dividers. */
  getCells?: (row: HTMLElement) => HTMLElement[];
}

export function useGridNav(
  rootRef: Ref<HTMLElement | null>,
  options: UseGridNavOptions = {},
) {
  const rowSelector = options.rowSelector ?? ".card-row__track";
  const getCells =
    options.getCells ??
    ((row: HTMLElement) =>
      Array.from(row.children).filter(
        (c): c is HTMLElement => c instanceof HTMLElement,
      ));
  const { modality } = useInputModality();
  const route = useRoute();
  const focusStore = storeFocusRestoration();
  let preferredCol = 0;

  // Walk up from `node` looking for a `[data-focus-key]` carrier. Tiles
  // mark their root with this so focus can survive navigation.
  function focusKeyOf(node: HTMLElement | null): string | null {
    let cursor: HTMLElement | null = node;
    while (cursor && cursor !== rootRef.value) {
      const key = cursor.getAttribute("data-focus-key");
      if (key) return key;
      cursor = cursor.parentElement;
    }
    return null;
  }

  function rows(): HTMLElement[] {
    if (options.getRows) return options.getRows();
    if (!rootRef.value) return [];
    return Array.from(rootRef.value.querySelectorAll<HTMLElement>(rowSelector));
  }

  function cells(row: HTMLElement): HTMLElement[] {
    return getCells(row);
  }

  function focusableIn(el: HTMLElement): HTMLElement {
    if (el.matches(FOCUSABLE_SELECTOR)) return el;
    const inner = el.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    return inner ?? el;
  }

  // Every focusable inside a cell: the cell's own focusable (a card
  // link / list-row anchor) plus any nested ones. A GameCard nests its
  // hidden hover-overlay actions (play / download / favorite / more /
  // platform icon) here — all natural tab stops even while invisible,
  // so they must be swept out of the tab order alongside the card link.
  function cellFocusables(cell: HTMLElement): HTMLElement[] {
    const out: HTMLElement[] = [];
    if (cell.matches(FOCUSABLE_SELECTOR)) out.push(cell);
    cell
      .querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      .forEach((el) => out.push(el));
    return out;
  }

  // A cell's nested action controls: everything focusable inside it EXCEPT
  // the primary (card link). For a GameCard these are the hover-overlay
  // buttons (play / download / favorite / more / status) — kept out of the
  // Tab order by `markRoving`, reached instead via gamepad X/Y.
  function cellActions(cell: HTMLElement): HTMLElement[] {
    const primary = focusableIn(cell);
    return cellFocusables(cell).filter((el) => el !== primary);
  }

  // Roving tabindex — the whole grid is ONE tab stop. `activePrimary`
  // (the card the user last touched, or the first one) gets tabindex="0";
  // every other focusable in every cell drops to "-1". So Tab enters the
  // grid on the active card and the next Tab leaves to the following
  // region (AlphaStrip, nav) instead of walking hundreds of cards and
  // their hidden action buttons. Arrow keys do the in-grid 2D nav.
  function markRoving(activePrimary: HTMLElement | null) {
    for (const row of rows()) {
      for (const cell of cells(row)) {
        for (const el of cellFocusables(cell)) {
          if (el === activePrimary) {
            el.setAttribute("tabindex", "0");
            el.setAttribute("data-grid-nav-cell", "");
          } else {
            el.setAttribute("tabindex", "-1");
            el.removeAttribute("data-grid-nav-cell");
          }
        }
      }
    }
  }

  // Which cell should own the tab stop right now, in priority order:
  // whatever currently holds focus inside the grid (so scrolling / late
  // mounts never steal focus), then the previously-marked cell if still
  // in the DOM, then the tile saved for this route, then the first cell.
  function activeCell(): HTMLElement | null {
    const rs = rows();
    if (rs.length === 0) return null;

    const active = document.activeElement;
    const marked =
      rootRef.value?.querySelector<HTMLElement>("[data-grid-nav-cell]") ?? null;
    const savedKey = focusStore.restore(route.fullPath);

    let firstCell: HTMLElement | null = null;
    let markedCell: HTMLElement | null = null;
    let savedCell: HTMLElement | null = null;

    for (const row of rs) {
      for (const cell of cells(row)) {
        if (
          active instanceof Node &&
          (cell === active || cell.contains(active))
        )
          return cell;
        if (!firstCell) firstCell = cell;
        if (marked && (cell === marked || cell.contains(marked)))
          markedCell = cell;
        if (savedKey && !savedCell && focusKeyOf(cell) === savedKey)
          savedCell = cell;
      }
    }
    return markedCell ?? savedCell ?? firstCell;
  }

  // (Re)establish the single tab stop against the current DOM. Cheap and
  // idempotent — safe to call on mount and whenever rows mount / unmount.
  function syncRoving() {
    const cell = activeCell();
    if (!cell) return;
    markRoving(focusableIn(cell));
  }

  function current(): { rowIdx: number; colIdx: number } | null {
    const active = document.activeElement as HTMLElement | null;
    if (!active) return null;
    const rs = rows();
    for (let r = 0; r < rs.length; r++) {
      const row = rs[r];
      if (!row.contains(active) && active !== row) continue;
      const cs = cells(row);
      for (let c = 0; c < cs.length; c++) {
        if (cs[c].contains(active) || cs[c] === active) {
          return { rowIdx: r, colIdx: c };
        }
      }
    }
    return null;
  }

  function focusAt(
    rowIdx: number,
    colIdx: number,
    opts: { verticalJump?: boolean } = {},
  ) {
    const rs = rows();
    const row = rs[rowIdx];
    if (!row) return;
    const cs = cells(row);
    if (cs.length === 0) return;
    const clamped = Math.min(Math.max(colIdx, 0), cs.length - 1);
    const cell = cs[clamped];
    const target = focusableIn(cell);

    // Point the roving tab stop at this cell before focusing it, so Tab
    // from outside always lands here and Shift+Tab escapes cleanly.
    markRoving(target);

    target.focus({ preventScroll: true });

    // Jumping rows (up/down): centre the whole section vertically so the
    // focused row reads as the page's centrepiece rather than hugging the
    // top edge. Staying in the same row (left/right): horizontal-only
    // scroll inside the track, and `block: "nearest"` so we don't jitter
    // the page vertically while scrubbing across cards.
    if (opts.verticalJump) {
      const section = cell.closest(".card-row") ?? row;
      section.scrollIntoView({ block: "center", behavior: "smooth" });
    } else {
      target.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: "smooth",
      });
    }
  }

  function focusFirst() {
    const rs = rows();
    for (let r = 0; r < rs.length; r++) {
      if (cells(rs[r]).length > 0) {
        preferredCol = 0;
        focusAt(r, 0, { verticalJump: true });
        return;
      }
    }
  }

  // Restore focus to the tile the user had selected last time they were
  // on this route. Walks every (row, cell) pair looking for one whose
  // `[data-focus-key]` matches the saved value. Falls back to `null`
  // when the saved tile is gone (filter changed, item deleted, …); the
  // caller is responsible for the `focusFirst` fallback.
  function focusSaved(): boolean {
    const savedKey = focusStore.restore(route.fullPath);
    if (!savedKey) return false;
    const rs = rows();
    for (let r = 0; r < rs.length; r++) {
      const cs = cells(rs[r]);
      for (let c = 0; c < cs.length; c++) {
        if (focusKeyOf(cs[c]) === savedKey) {
          preferredCol = c;
          focusAt(r, c, { verticalJump: true });
          return true;
        }
      }
    }
    return false;
  }

  function onKey(e: KeyboardEvent) {
    if (!rootRef.value) return;
    // Only steer when focus is already inside the grid — don't hijack
    // keys meant for input fields, menus, or other widgets.
    const active = document.activeElement;
    if (!(active instanceof Node) || !rootRef.value.contains(active)) return;

    const cur = current();
    if (!cur) return;

    const rs = rows();
    const cell = cells(rs[cur.rowIdx])[cur.colIdx];
    const primary = focusableIn(cell);
    const actions = cellActions(cell);
    const onAction =
      active !== primary && actions.includes(active as HTMLElement);

    // ── Inside a card's action row ──────────────────────────────────
    // The user descended into the overlay actions (gamepad X/Y, handled
    // in `onGamepadButton`). Arrows move between the actions; Escape (pad
    // B) returns to the card. `stopImmediatePropagation` so neither the
    // card→card nav nor the shell's Escape-clears-selection also fire.
    if (onAction) {
      const i = actions.indexOf(active as HTMLElement);
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
        primary.focus();
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        e.stopImmediatePropagation();
        actions[Math.min(i + 1, actions.length - 1)]?.focus();
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        e.stopImmediatePropagation();
        actions[Math.max(i - 1, 0)]?.focus();
      }
      return;
    }

    // ── Card → card 2D nav ──────────────────────────────────────────
    let { rowIdx, colIdx } = cur;
    const rowCells = cells(rs[rowIdx]);
    let verticalJump = false;

    if (e.key === "ArrowLeft") {
      if (colIdx === 0) return;
      colIdx -= 1;
      preferredCol = colIdx;
    } else if (e.key === "ArrowRight") {
      if (colIdx === rowCells.length - 1) return;
      colIdx += 1;
      preferredCol = colIdx;
    } else if (e.key === "ArrowUp") {
      if (rowIdx === 0) return;
      rowIdx -= 1;
      colIdx = preferredCol;
      verticalJump = true;
    } else if (e.key === "ArrowDown") {
      if (rowIdx === rs.length - 1) return;
      rowIdx += 1;
      colIdx = preferredCol;
      verticalJump = true;
    } else {
      return;
    }

    e.preventDefault();
    focusAt(rowIdx, colIdx, { verticalJump });
  }

  // Gamepad X / Y → descend into the focused card's action row (the pad
  // equivalent of the ContextMenu key). useGamepad fires this on window;
  // the synthetic arrow keydowns it also dispatches then flow through
  // `onKey` above, so navigating the action row works on a pad too.
  function onGamepadButton(e: Event) {
    const name = (e as CustomEvent<{ name?: string }>).detail?.name;
    if (name !== "x" && name !== "y") return;
    if (!rootRef.value) return;
    const active = document.activeElement;
    if (!(active instanceof Node) || !rootRef.value.contains(active)) return;
    const cur = current();
    if (!cur) return;
    const cell = cells(rows()[cur.rowIdx])[cur.colIdx];
    // Only enter from the card itself, not when already on an action.
    if (active !== focusableIn(cell)) return;
    const actions = cellActions(cell);
    if (actions.length > 0) actions[0].focus();
  }

  // Watches card rows for late-arriving children (data fetching finishes
  // after mount, skeletons swap to real cards). When the first cell shows
  // up — and the user is in pad modality without focus in the grid — we
  // land focus on it.
  let observer: MutationObserver | null = null;

  // Coalesce roving + autofocus into one rAF so a burst of row mounts
  // during a fast scroll doesn't sweep the whole grid per mutation.
  let refreshRaf = 0;
  function scheduleRefresh() {
    if (refreshRaf) return;
    refreshRaf = requestAnimationFrame(() => {
      refreshRaf = 0;
      syncRoving();
      maybeAutofocus();
    });
  }

  function maybeAutofocus() {
    if (modality.value !== "pad") return;
    if (!rootRef.value) return;
    if (rootRef.value.contains(document.activeElement)) return;
    if (focusSaved()) return;
    focusFirst();
  }

  // Capture the active tile's `[data-focus-key]` whenever focus moves
  // inside the grid (arrow nav, mouse, click). The next mount on this
  // same route restores it.
  function onFocusIn(e: FocusEvent) {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (!rootRef.value?.contains(target)) return;
    const key = focusKeyOf(target);
    if (key) focusStore.save(route.fullPath, key);
  }

  onMounted(() => {
    window.addEventListener("keydown", onKey);
    window.addEventListener("focusin", onFocusIn);
    window.addEventListener("gamepad:buttondown", onGamepadButton);
    if (rootRef.value) {
      observer = new MutationObserver(scheduleRefresh);
      observer.observe(rootRef.value, { childList: true, subtree: true });
    }
    scheduleRefresh();
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("focusin", onFocusIn);
    window.removeEventListener("gamepad:buttondown", onGamepadButton);
    observer?.disconnect();
    observer = null;
    if (refreshRaf) cancelAnimationFrame(refreshRaf);
    refreshRaf = 0;
  });

  // Reactively autofocus when modality becomes "pad". Useful when the
  // user picks up a gamepad after loading the page with the mouse.
  watch(modality, (m) => {
    if (m === "pad") maybeAutofocus();
  });

  return { focusFirst, focusAt };
}
