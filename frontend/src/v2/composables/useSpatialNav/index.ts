// useSpatialNav: moves focus by arrow key (and so by D-pad) for keys no grid
// or widget claimed with preventDefault, such as a move off a grid's edge.
// The grids listen on `document`, which an event reaches before `window`.
import { useEventListener } from "@vueuse/core";
import { onBeforeUnmount } from "vue";
import storePlaying from "@/stores/playing";
import { isPadEvent } from "@/v2/composables/useGamepad";
import {
  hasOpenEscapable,
  topEscapablePanel,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import { focusFromInput } from "@/v2/utils/autofocus";
import {
  ARROW_DIRECTIONS,
  FOCUSABLE_SELECTOR,
  pickSpatialTarget,
  type SpatialDirection,
} from "@/v2/utils/spatialNav";

// Input types whose arrow keys don't belong to the field.
const BUTTON_LIKE_INPUTS = new Set(["button", "checkbox", "reset", "submit"]);

// Single-line inputs whose arrows only move a caret.
const TEXT_INPUTS = new Set([
  "email",
  "password",
  "search",
  "tel",
  "text",
  "url",
]);

// Roles whose arrow keys belong to the widget itself.
const ARROW_OWNING_ROLES = new Set([
  "combobox",
  "grid",
  "gridcell",
  "listbox",
  "menuitem",
  "menuitemcheckbox",
  "menuitemradio",
  "option",
  "radio",
  "slider",
  "spinbutton",
  "textbox",
  "tree",
  "treeitem",
]);

// An open popup's activator, such as RSelect's, steers its list by arrow.
function hasOpenPopup(el: HTMLElement): boolean {
  const popup = el.getAttribute("aria-haspopup");
  return (
    !!popup && popup !== "false" && el.getAttribute("aria-expanded") === "true"
  );
}

function ownsArrowKeys(el: HTMLElement): boolean {
  if (el.isContentEditable || hasOpenPopup(el)) return true;
  if (el instanceof HTMLInputElement) return !BUTTON_LIKE_INPUTS.has(el.type);
  if (el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement) {
    return true;
  }
  return ARROW_OWNING_ROLES.has(el.getAttribute("role") ?? "");
}

function isTextField(
  el: HTMLElement,
): el is HTMLInputElement | HTMLTextAreaElement {
  if (hasOpenPopup(el)) return false;
  if (el instanceof HTMLTextAreaElement) return true;
  return el instanceof HTMLInputElement && TEXT_INPUTS.has(el.type);
}

const graphemes =
  typeof Intl.Segmenter === "function"
    ? new Intl.Segmenter(undefined, { granularity: "grapheme" })
    : null;

// The caret one character over in `dir`, or -1 past the text's edge. Steps
// whole graphemes so it never splits an emoji or an accent.
function nextCaret(text: string, at: number, dir: "left" | "right"): number {
  if (dir === "left") {
    if (at <= 0) return -1;
    return graphemes?.segment(text).containing(at - 1)?.index ?? at - 1;
  }
  if (at >= text.length) return -1;
  const seg = graphemes?.segment(text).containing(at);
  return seg ? seg.index + seg.segment.length : at + 1;
}

// Steps the caret for a D-pad press, which the browser won't do for a synthetic
// key. False when the press should move focus instead.
function stepCaret(
  el: HTMLInputElement | HTMLTextAreaElement,
  dir: SpatialDirection,
): boolean {
  // A read-only field, such as RDateField's, shows no caret to step.
  if (dir === "up" || dir === "down" || el.readOnly) return false;
  let start: number | null;
  let end: number | null;
  // Some input types (email) report null, older engines throw.
  try {
    ({ selectionStart: start, selectionEnd: end } = el);
  } catch {
    return false;
  }
  if (start === null || end === null) return false;
  if (start !== end) {
    const edge = dir === "left" ? start : end;
    el.setSelectionRange(edge, edge);
    return true;
  }
  const next = nextCaret(el.value, start, dir);
  if (next < 0) return false;
  el.setSelectionRange(next, next);
  return true;
}

function isNavigable(el: HTMLElement): boolean {
  if (el.closest("[inert], [aria-hidden='true']")) return false;
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return false;
  return getComputedStyle(el).visibility !== "hidden";
}

function isFixed(el: HTMLElement): boolean {
  for (let node: HTMLElement | null = el; node; node = node.parentElement) {
    if (getComputedStyle(node).position === "fixed") return true;
  }
  return false;
}

// Visible and not covered by fixed chrome such as the top bar.
function isInView(el: HTMLElement): boolean {
  const rect = el.getBoundingClientRect();
  if (rect.top < 0 || rect.bottom > window.innerHeight) return false;
  if (rect.left < 0 || rect.right > window.innerWidth) return false;
  if (typeof document.elementFromPoint !== "function") return true;
  const hit = document.elementFromPoint(
    (rect.left + rect.right) / 2,
    (rect.top + rect.bottom) / 2,
  );
  return !hit || el.contains(hit) || hit.contains(el);
}

/** Moves focus from `from` to the nearest control in `dir` under `scope`. */
export function moveFocus(
  from: HTMLElement,
  dir: SpatialDirection,
  scope: ParentNode = document,
): boolean {
  const candidates = Array.from(
    scope.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  )
    .filter((el) => el !== from && !el.contains(from) && isNavigable(el))
    .map((el) => ({ item: el, box: el.getBoundingClientRect() }));
  const target = pickSpatialTarget(
    from.getBoundingClientRect(),
    candidates,
    dir,
  );
  if (!target) return false;
  focusFromInput(target, { preventScroll: true });
  if (!isFixed(target) && !isInView(target)) {
    // Centring vertical moves keeps the target clear of the fixed bars.
    const vertical = dir === "up" || dir === "down";
    target.scrollIntoView({
      block: vertical ? "center" : "nearest",
      inline: "nearest",
      behavior: "smooth",
    });
  }
  return true;
}

let installed = false;

export function useSpatialNav() {
  function install() {
    if (installed) return;
    if (typeof window === "undefined") return;
    installed = true;

    const playingStore = storePlaying();

    function onKey(e: KeyboardEvent) {
      const dir = ARROW_DIRECTIONS[e.key];
      if (!dir || e.defaultPrevented) return;
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const active = document.activeElement;
      if (!(active instanceof HTMLElement) || active === document.body) return;
      // Ahead of the overlay check: RComboboxField's suggestions panel is an
      // overlay that doesn't contain its input.
      if (isPadEvent(e) && isTextField(active)) {
        if (stepCaret(active, dir)) {
          e.preventDefault();
          return;
        }
      } else if (ownsArrowKeys(active)) {
        return;
      }
      // An open overlay, a dialog over a game included, keeps focus inside
      // its own panel; otherwise a running game reads the arrows itself.
      let scope: ParentNode = document;
      if (hasOpenEscapable()) {
        const panel = topEscapablePanel();
        if (!panel?.contains(active)) return;
        scope = panel;
      } else if (playingStore.playing) {
        return;
      }
      if (moveFocus(active, dir, scope)) e.preventDefault();
    }

    useEventListener(window, "keydown", onKey);

    onBeforeUnmount(() => {
      installed = false;
    });
  }

  return { install };
}
