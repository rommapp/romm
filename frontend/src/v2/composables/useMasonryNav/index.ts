// useMasonryNav
//
// 2D arrow / gamepad navigation for the gallery's column-masonry grid.
// Unlike `useGridNav` (aligned card rows) and `useWrapGridNav` (a wrapping
// grid whose cells share a row `top`), masonry cards are vertically
// staggered: a "row" never has a single shared `top`. So row reconstruction
// from rects doesn't work here. Instead this picks the nearest focusable
// card in the pressed direction by comparing card-centre geometry — the
// standard spatial-navigation approach, which is layout-agnostic.
//
// Shares the rest of `useGridNav`'s contract: roving tabindex (only the
// active card is a tab stop), focus restoration per route via
// `[data-focus-key]`, and auto-focus of the first card when the input
// modality flips to `pad`. `useGamepad` dispatches synthetic Arrow events,
// so gamepad users transparently benefit from the keyboard code.
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

// Cross-axis drift is penalised relative to on-axis distance so movement
// favours the visually-aligned neighbour without ever getting stuck when a
// perfectly-aligned one doesn't exist (masonry rarely aligns exactly).
const CROSS_AXIS_WEIGHT = 2;

type Direction = "left" | "right" | "up" | "down";

interface Cell {
  el: HTMLElement;
  cx: number;
  cy: number;
}

export interface UseMasonryNavOptions {
  /** CSS selector for the focusable cards within the root. */
  cellSelector: string;
}

export function useMasonryNav(
  rootRef: Ref<HTMLElement | null>,
  options: UseMasonryNavOptions,
) {
  const { cellSelector } = options;
  const { modality } = useInputModality();
  const route = useRoute();
  const focusStore = storeFocusRestoration();

  function focusKeyOf(node: HTMLElement | null): string | null {
    let cursor: HTMLElement | null = node;
    while (cursor && cursor !== rootRef.value) {
      const key = cursor.getAttribute("data-focus-key");
      if (key) return key;
      cursor = cursor.parentElement;
    }
    return null;
  }

  function cells(): Cell[] {
    if (!rootRef.value) return [];
    const out: Cell[] = [];
    const found = Array.from(
      rootRef.value.querySelectorAll<HTMLElement>(cellSelector),
    );
    for (const el of found) {
      // Skip cards detached from layout (display:none) — never a target.
      if (el.offsetParent === null && el !== document.activeElement) continue;
      const r = el.getBoundingClientRect();
      out.push({ el, cx: r.left + r.width / 2, cy: r.top + r.height / 2 });
    }
    return out;
  }

  function focusableIn(el: HTMLElement): HTMLElement {
    if (el.matches(FOCUSABLE_SELECTOR)) return el;
    return el.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) ?? el;
  }

  /** The card element (matching `cellSelector`) that currently holds
   *  focus, or null when focus is elsewhere. */
  function activeCell(): HTMLElement | null {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !rootRef.value?.contains(active)) {
      return null;
    }
    return active.closest<HTMLElement>(cellSelector);
  }

  function setRoving(target: HTMLElement) {
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

  function focusCell(el: HTMLElement, opts: { center?: boolean } = {}) {
    const target = focusableIn(el);
    setRoving(target);
    target.focus({ preventScroll: true });
    target.scrollIntoView({
      block: opts.center ? "center" : "nearest",
      inline: "nearest",
      behavior: "smooth",
    });
  }

  /** Nearest card to `from` in `dir`, scored by on-axis distance plus a
   *  weighted cross-axis penalty. Returns null at the boundary. */
  function nearest(from: Cell, dir: Direction): HTMLElement | null {
    let best: HTMLElement | null = null;
    let bestScore = Infinity;
    for (const c of cells()) {
      if (c.el === from.el) continue;
      const dx = c.cx - from.cx;
      const dy = c.cy - from.cy;
      let onAxis: number;
      let crossAxis: number;
      if (dir === "left") {
        if (dx >= -1) continue;
        onAxis = -dx;
        crossAxis = Math.abs(dy);
      } else if (dir === "right") {
        if (dx <= 1) continue;
        onAxis = dx;
        crossAxis = Math.abs(dy);
      } else if (dir === "up") {
        if (dy >= -1) continue;
        onAxis = -dy;
        crossAxis = Math.abs(dx);
      } else {
        if (dy <= 1) continue;
        onAxis = dy;
        crossAxis = Math.abs(dx);
      }
      const score = onAxis + crossAxis * CROSS_AXIS_WEIGHT;
      if (score < bestScore) {
        bestScore = score;
        best = c.el;
      }
    }
    return best;
  }

  function onKey(e: KeyboardEvent) {
    let dir: Direction | null = null;
    if (e.key === "ArrowLeft") dir = "left";
    else if (e.key === "ArrowRight") dir = "right";
    else if (e.key === "ArrowUp") dir = "up";
    else if (e.key === "ArrowDown") dir = "down";
    if (!dir || !rootRef.value) return;

    const active = document.activeElement;
    if (!(active instanceof Node) || !rootRef.value.contains(active)) return;

    const cell = activeCell();
    if (!cell) return;
    const r = cell.getBoundingClientRect();
    const from: Cell = {
      el: cell,
      cx: r.left + r.width / 2,
      cy: r.top + r.height / 2,
    };
    const target = nearest(from, dir);
    if (!target) return;
    e.preventDefault();
    focusCell(target, { center: dir === "up" || dir === "down" });
  }

  function focusFirst() {
    const cs = cells();
    if (cs.length === 0) return;
    // Top-left-most card is the natural entry point.
    let first = cs[0];
    for (const c of cs) {
      if (
        c.cy < first.cy - 1 ||
        (Math.abs(c.cy - first.cy) <= 1 && c.cx < first.cx)
      ) {
        first = c;
      }
    }
    focusCell(first.el, { center: true });
  }

  function focusSaved(): boolean {
    const savedKey = focusStore.restore(route.fullPath);
    if (!savedKey) return false;
    for (const c of cells()) {
      if (focusKeyOf(c.el) === savedKey) {
        focusCell(c.el, { center: true });
        return true;
      }
    }
    return false;
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

  return { focusFirst };
}
