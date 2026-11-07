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
const NAME_PREFIX = "r-result-";
const ENTER_STAGGER_MS = 28;
const ENTER_STAGGER_CAP = 12;

interface Options {
  /** The scroller holding the cards. */
  container: () => HTMLElement | null;
  /** Viewport y below which a card is visible (under any sticky chrome). */
  visibleTop: () => number;
  /** Whether arriving cards fade in through the transition. A layout whose
   *  cards already animate on mount opts out so they don't play twice. */
  animateEntering: () => boolean;
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
    html.classList.add(ROOT_CLASS);
    nameAll(before, new Set(before.keys()));

    const stagger = document.createElement("style");
    const transition = document.startViewTransition(async () => {
      clearNames();
      apply();
      await nextTick();
      const after = visibleCards(root, opts.visibleTop());
      const entering = [...after.keys()].filter((id) => !before.has(id));
      const keep = new Set([...after.keys()].filter((id) => before.has(id)));
      if (opts.animateEntering()) {
        for (const id of entering) keep.add(id);
        stagger.textContent = entering
          .slice(0, ENTER_STAGGER_CAP)
          .map(
            (id, i) =>
              `::view-transition-new(${NAME_PREFIX}${id}){animation-delay:${i * ENTER_STAGGER_MS}ms}`,
          )
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
        html.classList.remove(ROOT_CLASS);
        html.style.removeProperty("--r-results-vt-from");
      });
    // A skipped transition still runs the update, so only wait for it.
    await transition.updateCallbackDone.catch(() => {});
  }

  return { run };
}
