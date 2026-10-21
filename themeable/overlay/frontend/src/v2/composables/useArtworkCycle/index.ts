// useArtworkCycle (romm-themeable): steps through pack ids at random for Branding's Random
// preview. The next pack's images load before it is shown, and the cycle holds still while
// the tab is hidden or reduced motion is on.
import { useDocumentVisibility, useIntervalFn } from "@vueuse/core";
import {
  computed,
  ref,
  toValue,
  watch,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from "vue";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";

/** A random id other than `current`, unless it is the only one. */
export function pickOther(
  ids: string[],
  current: string | null,
  random: () => number = Math.random,
): string | null {
  const pool = ids.length > 1 ? ids.filter((id) => id !== current) : ids;
  return pool[Math.floor(random() * pool.length)] ?? null;
}

export function useArtworkCycle(
  ids: MaybeRefOrGetter<string[]>,
  intervalMs: MaybeRefOrGetter<number>,
  {
    preload = () => Promise.resolve(),
    random = Math.random,
  }: {
    preload?: (id: string) => Promise<unknown>;
    random?: () => number;
  } = {},
): { current: Ref<string | null>; cycling: ComputedRef<boolean> } {
  const { enabled: reducedMotion } = useReducedMotion();
  const visibility = useDocumentVisibility();
  const current = ref<string | null>(pickOther(toValue(ids), null, random));
  const cycling = computed(
    () =>
      toValue(ids).length > 1 &&
      !reducedMotion.value &&
      visibility.value === "visible",
  );

  let loading = false;
  async function step(): Promise<void> {
    const next = pickOther(toValue(ids), current.value, random);
    if (loading || !next) return;
    loading = true;
    try {
      await preload(next);
    } catch {
      return;
    } finally {
      loading = false;
    }
    if (cycling.value) current.value = next;
  }

  const timer = useIntervalFn(() => void step(), intervalMs, {
    immediate: false,
  });
  watch(cycling, (on) => (on ? timer.resume() : timer.pause()), {
    immediate: true,
  });
  watch(
    () => toValue(ids),
    (list) => {
      if (!current.value || !list.includes(current.value)) {
        current.value = pickOther(list, null, random);
      }
    },
  );

  return { current, cycling };
}
