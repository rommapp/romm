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
//   * Home / End → first / last cell in the row; with Ctrl (or a row of
//     one cell), the first cell of the grid / the last.
//   * PageUp / PageDown → same column, one viewport of rows up / down.
//   * On autofocus we remember a "preferred column" and restore it when
//     moving up/down through rows of different lengths, a common media-UI
//     pattern so row switching doesn't permanently lose horizontal place.
//
// Integration:
//   * Input modality flipping to `"pad"` (gamepad connected / pressed)
//     autofocuses the first cell, so `useGamepad`'s synthetic arrow keys
//     immediately land somewhere useful.
//   * A key that would leave the grid (up from the first row, …) is left
//     unclaimed, so `useSpatialNav` carries focus to the next region.
//   * `useGamepad` itself dispatches keydowns, so everything here is
//     plain keyboard code; gamepad users transparently benefit.
//
// For wrapping CSS grids (PlatformsIndex / CollectionsIndex), where
// there are no per-row DOM containers, use `useWrapGridNav` instead;
// it detects rows spatially from cell rects.
import { useEventListener, useMutationObserver } from "@vueuse/core";
import { onBeforeUnmount, onMounted, watch, type Ref } from "vue";
import { useRoute } from "vue-router";
import { useInputModality } from "@/v2/composables/useInputModality";
import storeFocusRestoration from "@/v2/stores/focusRestoration";
import { FOCUSABLE_SELECTOR } from "@/v2/utils/spatialNav";

export interface UseGridNavOptions {
  /** Selector that resolves to one DOM element per logical row.
   *  Defaults to `.card-row__track` (CardRow's scroll track). Ignored
   *  when `getRows` is provided. */
  rowSelector?: string;
  /** Returns the row elements. Overrides `rowSelector`. Useful when
   *  the root element itself IS the only row (single-row toolbars
   *  like GameDetails' action ribbon): pass `() => [rootEl.value!]`. */
  getRows?: () => HTMLElement[];
  /** Returns the cells of a given row. Defaults to the row's direct
   *  children. Pass `(row) => [row]` for list-mode rows where the row
   *  element itself is the single focusable cell, or a custom selector
   *  to skip non-focusable spacers / dividers. */
  getCells?: (row: HTMLElement) => HTMLElement[];
  /** Keep a single tab stop in the grid, as the ARIA grid pattern asks:
   *  the controls of the active cell stay tabbable and every other cell's
   *  get `tabindex="-1"`, including cells that mount later. */
  roving?: boolean;
  /** Renders the grid's first or last row when it virtualises its rows, so
   *  Ctrl+Home / Ctrl+End can reach rows that aren't mounted. */
  revealEdge?: (edge: "first" | "last") => void;
}

const GRID_KEYS = new Set([
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
]);

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

// Height of the box the grid scrolls in, which is one page of rows.
function pageHeight(el: HTMLElement): number {
  for (let node = el.parentElement; node; node = node.parentElement) {
    const overflow = getComputedStyle(node).overflowY;
    if (overflow === "auto" || overflow === "scroll") return node.clientHeight;
  }
  return window.innerHeight;
}

// Controls the roving mode may take out of the tab order. Unlike
// FOCUSABLE_SELECTOR, this still matches them once they are at -1.
const ROVING_CANDIDATES = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]",
].join(",");
// The tabindex a control had before the roving mode touched it.
const ROVING_ORIGINAL = "data-grid-roving";

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
  let activeKey: string | null = null;
  // The cell this composable last focused, to tell when focus arrived another
  // way (a click) and the remembered column no longer applies.
  let navCell: HTMLElement | null = null;

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

  // A cell's own `[data-focus-key]`, or that of the tile inside it.
  function cellKey(cell: HTMLElement): string | null {
    return (
      cell.getAttribute("data-focus-key") ??
      cell.querySelector("[data-focus-key]")?.getAttribute("data-focus-key") ??
      null
    );
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
    const selector = options.roving ? ROVING_CANDIDATES : FOCUSABLE_SELECTOR;
    if (el.matches(selector)) return el;
    const inner = el.querySelector<HTMLElement>(selector);
    return inner ?? el;
  }

  // The controls of a cell that are tabbable on their own, so the roving
  // mode leaves alone the ones a component already took out of the order.
  function rovingControls(cell: HTMLElement): HTMLElement[] {
    const found = Array.from(
      cell.querySelectorAll<HTMLElement>(ROVING_CANDIDATES),
    );
    if (cell.matches(ROVING_CANDIDATES)) found.unshift(cell);
    return found.filter((el) => {
      if (!el.hasAttribute(ROVING_ORIGINAL)) {
        el.setAttribute(ROVING_ORIGINAL, el.getAttribute("tabindex") ?? "");
      }
      return el.getAttribute(ROVING_ORIGINAL) !== "-1";
    });
  }

  function syncRoving() {
    if (!options.roving) return;
    const allCells = rows().flatMap((row) => cells(row));
    const active =
      allCells.find((cell) => activeKey && cellKey(cell) === activeKey) ??
      allCells.find((cell) => rovingControls(cell).length > 0);
    for (const cell of allCells) {
      for (const el of rovingControls(cell)) {
        const original = el.getAttribute(ROVING_ORIGINAL) ?? "";
        if (cell !== active) el.setAttribute("tabindex", "-1");
        else if (original) el.setAttribute("tabindex", original);
        else el.removeAttribute("tabindex");
      }
    }
  }

  let syncFrame = 0;
  function scheduleSyncRoving() {
    if (!options.roving || syncFrame) return;
    syncFrame = requestAnimationFrame(() => {
      syncFrame = 0;
      syncRoving();
    });
  }

  function current(): { rowIdx: number; colIdx: number } | null {
    const active = document.activeElement as HTMLElement | null;
    if (!active) return null;
    const rs = rows();
    for (const [r, row] of rs.entries()) {
      if (!row.contains(active) && active !== row) continue;
      for (const [c, cell] of cells(row).entries()) {
        if (cell.contains(active) || cell === active) {
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
    const cell = cs[clamped]!;
    const target = focusableIn(cell);
    navCell = cell;

    // Roving tabindex: only the current cell is a tab stop, every other
    // cell sets tabindex="-1". Lets the user land on the last focused
    // card via Tab from outside the grid, and keeps Shift+Tab escape
    // behaviour clean. Borrowed from the v1 console useRovingDom.
    if (options.roving) {
      activeKey = cellKey(cell);
      syncRoving();
    } else {
      const previous = rootRef.value?.querySelectorAll<HTMLElement>(
        "[data-grid-nav-cell]",
      );
      previous?.forEach((other) => {
        other.setAttribute("tabindex", "-1");
        other.removeAttribute("data-grid-nav-cell");
      });
      target.setAttribute("data-grid-nav-cell", "");
      target.setAttribute("tabindex", "0");
    }

    // Firefox skips the focus ring on a script focus() after a mouse click.
    target.focus({ preventScroll: true, focusVisible: true });

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
    for (const [r, row] of rs.entries()) {
      if (cells(row).length > 0) {
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
    for (const [r, row] of rs.entries()) {
      for (const [c, cell] of cells(row).entries()) {
        if (cellKey(cell) === savedKey) {
          preferredCol = c;
          focusAt(r, c, { verticalJump: true });
          return true;
        }
      }
    }
    return false;
  }

  function hasControl(cell: HTMLElement): boolean {
    const selector = options.roving ? ROVING_CANDIDATES : FOCUSABLE_SELECTOR;
    return focusableIn(cell) !== cell || cell.matches(selector);
  }

  // Focuses the first or last cell that holds a control, skipping skeletons.
  function focusEdge(edge: "first" | "last") {
    const rs = rows();
    const order = edge === "first" ? rs.keys() : [...rs.keys()].reverse();
    for (const r of order) {
      const cs = cells(rs[r]!);
      const cols = edge === "first" ? cs.keys() : [...cs.keys()].reverse();
      for (const c of cols) {
        if (!hasControl(cs[c]!)) continue;
        preferredCol = c;
        focusAt(r, c, { verticalJump: true });
        return;
      }
    }
  }

  // Whether the outermost cell on `edge` holds a loaded control yet.
  function edgeLoaded(edge: "first" | "last"): boolean {
    const rs = rows();
    const row = edge === "first" ? rs[0] : rs[rs.length - 1];
    if (!row) return false;
    const cs = cells(row);
    const cell = edge === "first" ? cs[0] : cs[cs.length - 1];
    return !!cell && hasControl(cell);
  }

  async function jumpToEdge(edge: "first" | "last") {
    if (options.revealEdge) {
      options.revealEdge(edge);
      // Two frames for the scroll to mount the edge rows, then up to about
      // two seconds for their data to load.
      await nextFrame();
      await nextFrame();
      for (let i = 0; i < 120 && !edgeLoaded(edge); i++) await nextFrame();
    }
    focusEdge(edge);
  }

  // The row about one viewport above or below `from`, clamped to the rows
  // that are mounted.
  function pageRow(rs: HTMLElement[], from: number, dir: 1 | -1): number {
    const fromRow = rs[from]!;
    const top = fromRow.getBoundingClientRect().top;
    const target = top + dir * pageHeight(fromRow);
    let best = from;
    for (let r = from + dir; r >= 0 && r < rs.length; r += dir) {
      const rowTop = rs[r]!.getBoundingClientRect().top;
      if (dir === 1 ? rowTop > target : rowTop < target) break;
      best = r;
    }
    return best === from
      ? Math.min(Math.max(from + dir, 0), rs.length - 1)
      : best;
  }

  function onKey(e: KeyboardEvent) {
    if (!GRID_KEYS.has(e.key)) return;
    if (!rootRef.value) return;
    // Only steer when focus is already inside the grid; don't hijack
    // arrow keys meant for input fields, menus, or other widgets.
    const active = document.activeElement;
    if (!(active instanceof Node) || !rootRef.value.contains(active)) return;

    const cur = current();
    if (!cur) return;

    let { rowIdx, colIdx } = cur;
    const rs = rows();
    const rowCells = cells(rs[rowIdx]!);
    if (rowCells[colIdx] !== navCell) preferredCol = colIdx;
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
    } else if (e.key === "Home" || e.key === "End") {
      // A row of one cell has nowhere to go inside it, so it moves through
      // the grid instead.
      if (e.ctrlKey || e.metaKey || rowCells.length === 1) {
        e.preventDefault();
        void jumpToEdge(e.key === "Home" ? "first" : "last");
        return;
      }
      colIdx = e.key === "Home" ? 0 : rowCells.length - 1;
      preferredCol = colIdx;
    } else if (e.key === "PageUp" || e.key === "PageDown") {
      rowIdx = pageRow(rs, rowIdx, e.key === "PageDown" ? 1 : -1);
      colIdx = preferredCol;
      verticalJump = true;
    }

    e.preventDefault();
    focusAt(rowIdx, colIdx, { verticalJump });
  }

  // Runs as late children arrive (fetches finishing, skeletons swapping to
  // cards), so pad focus lands on the first cell once it shows up.
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
    if (options.roving) {
      const cell = rows()
        .flatMap((row) => cells(row))
        .find((c) => c.contains(target));
      const cellFocusKey = cell ? cellKey(cell) : null;
      if (cellFocusKey && cellFocusKey !== activeKey) {
        activeKey = cellFocusKey;
        syncRoving();
      }
    }
  }

  onMounted(() => {
    useEventListener(document, "keydown", onKey);
    useEventListener(window, "focusin", onFocusIn);
    useMutationObserver(
      rootRef,
      () => {
        scheduleSyncRoving();
        maybeAutofocus();
      },
      { childList: true, subtree: true },
    );
    requestAnimationFrame(maybeAutofocus);
    scheduleSyncRoving();
  });

  onBeforeUnmount(() => cancelAnimationFrame(syncFrame));

  // Reactively autofocus when modality becomes "pad". Useful when the
  // user picks up a gamepad after loading the page with the mouse.
  watch(modality, (m) => {
    if (m === "pad") maybeAutofocus();
  });

  return { focusFirst, focusAt };
}
