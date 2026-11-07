// useResultsTransition: animates a gallery result swap (a search or filter
// refetch) with a view transition. Cards in both results glide to their new
// slot, cards that left fade out, and cards that arrive fade in staggered.
// Only the named cards animate: the root opts out, so the toolbar and the
// search box stay live and typeable throughout.
import { nextTick } from "vue";
import { useReducedMotion } from "@/composables/useReducedMotion";
import { pendingMorphName } from "@/composables/useViewTransition";

/** Marks an element as one result card, valued by its ROM id. */
export const RESULT_ID_ATTR = "data-result-id";

const ROOT_CLASS = "r-results-vt";
const ROWS_CLASS = `${ROOT_CLASS}--rows`;
const NAME_PREFIX = "r-result-";
const ENTER_STAGGER_MS = 28;
const ENTER_STAGGER_CAP = 12;
// Leaving rows clear their slot before arriving rows fade into it.
const ROWS_ENTER_DELAY_MS = 100;

/** How a layout's items behave across a swap. `cards` remount on arrival and
 *  play their own fade; `rows` are reused in place, so arrivals fade in
 *  through the transition once the rows leaving their slot are gone. */
export type ResultsKind = "cards" | "rows";

interface Options {
  /** The scroller holding the cards. */
  container: () => HTMLElement | null;
  /** Viewport y below which a card is visible (under any sticky chrome). */
  visibleTop: () => number;
  kind: () => ResultsKind;
}

function supported(): boolean {
  return (
    typeof document !== "undefined" &&
    typeof document.startViewTransition === "function"
  );
}

/** Cards wholly inside the visible band, by ROM id. Partly hidden cards are
 *  left out so no snapshot paints over the sticky toolbar. */
function visibleCards(
  root: HTMLElement,
  top: number,
): Map<string, HTMLElement> {
  const out = new Map<string, HTMLElement>();
  const bottom = Math.min(
    window.innerHeight,
    root.getBoundingClientRect().bottom,
  );
  for (const el of root.querySelectorAll<HTMLElement>(`[${RESULT_ID_ATTR}]`)) {
    const id = el.getAttribute(RESULT_ID_ATTR);
    if (!id || out.has(id)) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.top >= top && r.bottom <= bottom) out.set(id, el);
  }
  return out;
}

export function useResultsTransition(opts: Options) {
  const { enabled: reducedMotion } = useReducedMotion();

  /** Runs `apply` (the swap) inside a view transition when one can run. */
  async function run(apply: () => void): Promise<void> {
    const root = opts.container();
    if (
      !root ||
      !supported() ||
      reducedMotion.value ||
      pendingMorphName.value !== null ||
      document.visibilityState === "hidden"
    ) {
      apply();
      return;
    }

    const before = visibleCards(root, opts.visibleTop());
    if (before.size === 0) {
      apply();
      return;
    }

    const named: HTMLElement[] = [];
    const nameAll = (cards: Map<string, HTMLElement>, keep: Set<string>) => {
      for (const [id, el] of cards) {
        if (!keep.has(id)) continue;
        el.style.viewTransitionName = `${NAME_PREFIX}${id}`;
        named.push(el);
      }
    };
    const clearNames = () => {
      for (const el of named) el.style.viewTransitionName = "";
      named.length = 0;
    };

    const html = document.documentElement;
    // The stale dim is on the cards' ancestor, which snapshots leave out.
    const body = root.querySelector<HTMLElement>("[data-stale]");
    html.style.setProperty(
      "--r-results-vt-from",
      body ? getComputedStyle(body).opacity : "1",
    );
    const rows = opts.kind() === "rows";
    html.classList.add(ROOT_CLASS);
    html.classList.toggle(ROWS_CLASS, rows);
    nameAll(before, new Set(before.keys()));

    const stagger = document.createElement("style");
    const transition = document.startViewTransition(async () => {
      clearNames();
      apply();
      await nextTick();
      const after = visibleCards(root, opts.visibleTop());
      const entering = [...after.keys()].filter((id) => !before.has(id));
      const keep = new Set([...after.keys()].filter((id) => before.has(id)));
      if (rows) {
        for (const id of entering) keep.add(id);
        // A named pseudo-element outranks the `(*)` rules in global.css,
        // so these delays win over their `animation` shorthand.
        stagger.textContent = entering
          .map((id, i) => {
            const delay =
              ROWS_ENTER_DELAY_MS +
              Math.min(i, ENTER_STAGGER_CAP) * ENTER_STAGGER_MS;
            return `html.${ROOT_CLASS}::view-transition-new(${NAME_PREFIX}${id}):only-child{animation-delay:${delay}ms}`;
          })
          .join("");
        document.head.appendChild(stagger);
      }
      nameAll(after, keep);
    });

    void transition.finished
      .catch(() => {})
      .finally(() => {
        clearNames();
        stagger.remove();
        html.classList.remove(ROOT_CLASS, ROWS_CLASS);
        html.style.removeProperty("--r-results-vt-from");
      });
    // A skipped transition still runs the update, so only wait for it.
    await transition.updateCallbackDone.catch(() => {});
  }

  return { run };
}
