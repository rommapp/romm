// Animates a gallery result swap with a view transition. Only the named
// cards animate; the root opts out so the search box stays live.
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

/** `cards` remount on arrival and play their own fade; `rows` are reused in
 *  place, so arrivals fade in through the transition. */
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

// Settles the running swap so its late cleanup can't clear a newer one's names.
let settleRunning: (() => void) | null = null;

export function useResultsTransition(opts: Options) {
  const { enabled: reducedMotion } = useReducedMotion();

  /** Runs `apply` (the swap) inside a view transition when one can run. */
  async function run(apply: () => void): Promise<void> {
    settleRunning?.();
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
    let settled = false;
    const settle = () => {
      if (settled) return;
      settled = true;
      transition.skipTransition();
      clearNames();
      stagger.remove();
      html.classList.remove(ROOT_CLASS, ROWS_CLASS);
      html.style.removeProperty("--r-results-vt-from");
      if (settleRunning === settle) settleRunning = null;
    };
    const transition = document.startViewTransition(async () => {
      clearNames();
      apply();
      await nextTick();
      if (settled) return;
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

    settleRunning = settle;
    // A preempted transition rejects all three promises.
    void transition.ready.catch(() => {});
    void transition.finished.catch(() => {}).finally(settle);
    // A skipped transition still runs the update, so only wait for it.
    await transition.updateCallbackDone.catch(() => {});
  }

  return { run };
}
