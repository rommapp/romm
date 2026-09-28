// useStaggeredEntrance: plays `.r-v2-asset-fade` on a row once its content is
// ready. Rows turning ready in the same tick cascade top to bottom; a row
// scrolled into view on its own fades in without waiting behind the others.
import { computed, type Ref, ref, watch } from "vue";

/** Past this many rows the cascade stops lengthening; they are offscreen. */
const MAX_STAGGER = 12;

interface Arrival {
  el: Ref<HTMLElement | null>;
  index: Ref<number>;
}

let batch: Arrival[] = [];

// Ranked once the tick's render has placed every row: Vue mounts a keyed
// batch bottom-up, so arrival order is no guide to the order on screen.
function settleBatch() {
  const arrivals = batch;
  batch = [];
  arrivals.sort(byDocumentOrder).forEach((arrival, rank) => {
    arrival.index.value = Math.min(rank, MAX_STAGGER);
  });
}

function byDocumentOrder(a: Arrival, b: Arrival): number {
  const first = a.el.value;
  const second = b.el.value;
  if (!first || !second) return 0;
  return first.compareDocumentPosition(second) &
    Node.DOCUMENT_POSITION_FOLLOWING
    ? -1
    : 1;
}

/**
 * Args:
 *   el: the row's root element.
 *   ready: whether the row has its content; the entrance plays each time it
 *     turns true. Omit it for a row that mounts with its content.
 */
export function useStaggeredEntrance(
  el: Ref<HTMLElement | null>,
  ready: () => boolean = () => true,
) {
  const entering = ref(false);
  const index = ref(0);

  watch(
    ready,
    (isReady) => {
      if (!isReady) return;
      if (batch.length === 0) queueMicrotask(settleBatch);
      batch.push({ el, index });
      entering.value = true;
    },
    { immediate: true },
  );

  return {
    entranceClass: computed(() => ({ "r-v2-asset-fade": entering.value })),
    entranceStyle: computed(() => ({ "--asset-fade-i": index.value })),
    /** Drops the class once it has played, so a keyed move (a re-sort)
     *  re-inserting the row doesn't replay it. Bind with `.self`. */
    endEntrance: () => {
      entering.value = false;
    },
  };
}
