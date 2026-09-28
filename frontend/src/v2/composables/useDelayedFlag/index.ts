// Mirrors a boolean source, but only turns true once the source has stayed
// true for `delayMs`, so fast work never paints a loader.
import {
  onScopeDispose,
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
  let timer: ReturnType<typeof setTimeout> | null = null;

  function clearTimer() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  watch(
    () => toValue(source),
    (on) => {
      clearTimer();
      const delay = toValue(delayMs);
      if (!on || delay <= 0) {
        flag.value = on;
        return;
      }
      timer = setTimeout(() => {
        timer = null;
        flag.value = true;
      }, delay);
    },
    { immediate: true },
  );

  onScopeDispose(clearTimer);

  return flag;
}
