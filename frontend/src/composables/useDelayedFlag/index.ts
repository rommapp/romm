// Mirrors a boolean source, but only turns true once the source has stayed
// true for `delayMs`, so fast work never paints a loader.
import { useTimeoutFn } from "@vueuse/core";
import {
  shallowRef,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type ShallowRef,
} from "vue";

export function useDelayedFlag(
  source: MaybeRefOrGetter<boolean>,
  delayMs: MaybeRefOrGetter<number>,
): Readonly<ShallowRef<boolean>> {
  const flag = shallowRef(false);
  const delayed = useTimeoutFn(
    () => {
      flag.value = true;
    },
    delayMs,
    { immediate: false },
  );

  watch(
    () => toValue(source),
    (on) => {
      delayed.stop();
      if (!on || toValue(delayMs) <= 0) {
        flag.value = on;
        return;
      }
      delayed.start();
    },
    { immediate: true },
  );

  return flag;
}
