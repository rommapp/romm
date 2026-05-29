// useWrapGridNav
//
// 2D arrow-key navigation for wrapping CSS grids — the layout
// PlatformsIndex / CollectionsIndex use:
//
//   .grid {
//     display: grid;
//     grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
//   }
//
// There are no per-row DOM containers; tiles wrap visually based on the
// viewport width. Rows are reconstructed at navigation time from each
// cell's `getBoundingClientRect().top` — cells with (approximately) the
// same top live on the same visual row. This handles:
//   * variable column count at different breakpoints
//   * multiple grouped grids in a single view (each group's grid sits
//     under a heading; ArrowDown crosses the heading naturally because
//     all cells across all groups feed the same rect-sorted pool)
//   * cells of slightly different heights (a 2px tolerance avoids
//     splitting a row when sub-pixel rounding differs)
//
// Mechanics mirror `useGridNav`: roving tabindex, "preferred column" so
// jumping rows doesn't permanently lose horizontal place, MutationObserver
// auto-focus while in pad modality, reactivity to modality flipping to
// pad mid-session.
//
// Integration: this is plain keyboard code; `useGamepad` dispatches
// synthetic Arrow events so gamepad users transparently benefit.
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

// Within this many CSS pixels two cells are considered to share a row.
// Tile heights are uniform per grid so anything within a couple of px is
// rounding noise.
const ROW_TOP_TOLERANCE = 2;

export interface UseWrapGridNavOptions {
  /** CSS selector for the focusable tiles within the root. Required —
   *  the composable can't guess what counts as a cell (the grid may also
   *  contain headings, panels, dividers, etc). */
  cellSelector: string;
}

export function useWrapGridNav(
  rootRef: Ref<HTMLElement | null>,
  options: UseWrapGridNavOptions,
) {
  const { cellSelector } = options;
  const { modality } = useInputModality();
  const route = useRoute();
  const focusStore = storeFocusRestoration();
  let preferredCol = 0;

  function focusKeyOf(node: HTMLElement | null): string | null {
    let cursor: HTMLElement | null = node;
    while (cursor && cursor !== rootRef.value) {
      const key = cursor.getAttribute("data-focus-key");
      if (key) return key;
      cursor = cursor.parentElement;
    }
    return null;
  }

  function allCells(): HTMLElement[] {
    if (!rootRef.value) return [];
    return Array.from(
      rootRef.value.querySelectorAll<HTMLElement>(cellSelector),
    ).filter((el) => el.offsetParent !== null);
  }

  // Group cells into rows by `boundingClientRect.top`. Cells inside the
  // root are read in DOM order, then re-sorted by (top, left) so the
  // navigation order tracks visual order. This matters when the grid is
  // sandwiched with headings or panels that interleave cells.
  function rows(): HTMLElement[][] {
    const cells = allCells();
    if (cells.length === 0) return [];
    const positioned = cells.map((el) => {
      const r = el.getBoundingClientRect();
      return { el, top: r.top, left: r.left };
    });
    positioned.sort((a, b) => {
      if (Math.abs(a.top - b.top) > ROW_TOP_TOLERANCE) return a.top - b.top;
      return a.left - b.left;
    });
    const out: HTMLElement[][] = [];
    let current: HTMLElement[] = [];
    let rowTop: number | null = null;
    for (const p of positioned) {
      if (rowTop === null || Math.abs(p.top - rowTop) <= ROW_TOP_TOLERANCE) {
        current.push(p.el);
        rowTop = rowTop === null ? p.top : rowTop;
      } else {
        out.push(current);
        current = [p.el];
        rowTop = p.top;
      }
    }
    if (current.length) out.push(current);
    return out;
  }

  function focusableIn(el: HTMLElement): HTMLElement {
    if (el.matches(FOCUSABLE_SELECTOR)) return el;
    const inner = el.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    return inner ?? el;
  }

  function current(): { rowIdx: number; colIdx: number } | null {
    const active = document.activeElement as HTMLElement | null;
    if (!active) return null;
    const rs = rows();
    for (let r = 0; r < rs.length; r++) {
      const cs = rs[r];
      for (let c = 0; c < cs.length; c++) {
        if (cs[c].contains(active) || cs[c] === active) {
          return { rowIdx: r, colIdx: c };
        }
      }
    }
    return null;
  }

  function focusAt(rowIdx: number, colIdx: number) {
    const rs = rows();
    const row = rs[rowIdx];
    if (!row) return;
    if (row.length === 0) return;
    const clamped = Math.min(Math.max(colIdx, 0), row.length - 1);
    const cell = row[clamped];
    const target = focusableIn(cell);

    // Roving tabindex — only the current cell is a tab stop. Mirrors
    // useGridNav's approach so Tab from outside the grid lands on the
    // last-focused tile.
    const previous = rootRef.value?.querySelectorAll<HTMLElement>(
      "[data-wrap-grid-cell]",
    );
    previous?.forEach((other) => {
      other.setAttribute("tabindex", "-1");
      other.removeAttribute("data-wrap-grid-cell");
    });
    target.setAttribute("data-wrap-grid-cell", "");
    target.setAttribute("tabindex", "0");

    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function focusFirst() {
    const rs = rows();
    if (rs.length === 0 || rs[0].length === 0) return;
    preferredCol = 0;
    focusAt(0, 0);
  }

  // Restore focus to whichever tile carried the saved `[data-focus-key]`
  // on this route the last time the user was here. Returns false when the
  // saved key has no match in the current view (filter changed, item
  // removed) — the caller falls back to `focusFirst`.
  function focusSaved(): boolean {
    const savedKey = focusStore.restore(route.fullPath);
    if (!savedKey) return false;
    const rs = rows();
    for (let r = 0; r < rs.length; r++) {
      for (let c = 0; c < rs[r].length; c++) {
        if (focusKeyOf(rs[r][c]) === savedKey) {
          preferredCol = c;
          focusAt(r, c);
          return true;
        }
      }
    }
    return false;
  }

  function onKey(e: KeyboardEvent) {
    if (
      e.key !== "ArrowLeft" &&
      e.key !== "ArrowRight" &&
      e.key !== "ArrowUp" &&
      e.key !== "ArrowDown"
    ) {
      return;
    }
    if (!rootRef.value) return;
    const active = document.activeElement;
    if (!(active instanceof Node) || !rootRef.value.contains(active)) return;

    const cur = current();
    if (!cur) return;

    const rs = rows();
    let { rowIdx, colIdx } = cur;
    const rowCells = rs[rowIdx];

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
    } else if (e.key === "ArrowDown") {
      if (rowIdx === rs.length - 1) return;
      rowIdx += 1;
      colIdx = preferredCol;
    }

    e.preventDefault();
    focusAt(rowIdx, colIdx);
  }

  let observer: MutationObserver | null = null;

  function maybeAutofocus() {
    if (modality.value !== "pad") return;
    if (!rootRef.value) return;
    if (rootRef.value.contains(document.activeElement)) return;
    if (focusSaved()) return;
    focusFirst();
  }

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
    if (rootRef.value) {
      observer = new MutationObserver(() => maybeAutofocus());
      observer.observe(rootRef.value, { childList: true, subtree: true });
    }
    requestAnimationFrame(maybeAutofocus);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("keydown", onKey);
    window.removeEventListener("focusin", onFocusIn);
    observer?.disconnect();
    observer = null;
  });

  watch(modality, (m) => {
    if (m === "pad") maybeAutofocus();
  });

  return { focusFirst, focusAt };
}
