// Picks skeleton, empty or content for a loading view. Until loading outlasts
// `delayMs` the last settled phase stays up, so a fast load never flashes.
import {
  nextTick,
  onScopeDispose,
  shallowRef,
  toValue,
  watchEffect,
  type MaybeRefOrGetter,
  type ShallowRef,
} from "vue";
import { useDelayedFlag } from "@/v2/composables/useDelayedFlag";

/** `idle` means nothing has settled yet and the skeleton isn't due: render nothing. */
export type LoadingPhase = "idle" | "skeleton" | "empty" | "content";

export const SKELETON_DELAY_MS = 200;
// Once painted, the skeleton stays this long so a load that lands just past
// the delay doesn't blink it.
export const SKELETON_MIN_MS = 300;

export function useLoadingPhase(
  loading: MaybeRefOrGetter<boolean>,
  empty: MaybeRefOrGetter<boolean>,
  delayMs: MaybeRefOrGetter<number> = SKELETON_DELAY_MS,
): Readonly<ShallowRef<LoadingPhase>> {
  const skeletonDue = useDelayedFlag(loading, delayMs);
  const phase = shallowRef<LoadingPhase>("idle");
  const holdingSkeleton = shallowRef(false);
  let holdTimer: ReturnType<typeof setTimeout> | null = null;
  // Empty at setup often means a fetch that only starts in onMounted, so the
  // first "empty" waits a tick for that load to begin.
  const ready = shallowRef(false);
  void nextTick(() => {
    ready.value = true;
  });

  watchEffect(() => {
    if (!toValue(loading)) {
      if (holdingSkeleton.value) return;
      const isEmpty = toValue(empty);
      if (isEmpty && !ready.value) return;
      phase.value = isEmpty ? "empty" : "content";
    } else if (skeletonDue.value && phase.value !== "skeleton") {
      phase.value = "skeleton";
      holdingSkeleton.value = true;
      holdTimer = setTimeout(() => {
        holdTimer = null;
        holdingSkeleton.value = false;
      }, SKELETON_MIN_MS);
    }
  });

  onScopeDispose(() => {
    if (holdTimer) clearTimeout(holdTimer);
  });

  return phase;
}
