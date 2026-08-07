// useIsAlive — tracks whether the owning effect scope is still active, so an
// async handler that resolves late can tell it's talking to a dead component.
//
// Replaces the manual pattern:
//   let unmounted = false;
//   onBeforeUnmount(() => { unmounted = true; });
//
// Cleanup uses `onScopeDispose` (not `onBeforeUnmount`) so it also works from
// a non-component effect scope, e.g. inside another composable.
//
// Note: VueUse's `useMounted` is not a substitute — it only flips to `true` on
// mount and never back to `false` on teardown.
import { onScopeDispose, shallowRef, type ShallowRef } from "vue";

export function useIsAlive(): ShallowRef<boolean> {
  const alive = shallowRef(true);
  onScopeDispose(() => {
    alive.value = false;
  });
  return alive;
}
