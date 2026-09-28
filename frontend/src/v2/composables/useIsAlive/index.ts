// useIsAlive — tracks whether the owning effect scope is still active, so an
// async handler that resolves late can tell it's talking to a dead component.
import { onScopeDispose, shallowRef, type ShallowRef } from "vue";

export function useIsAlive(): ShallowRef<boolean> {
  const alive = shallowRef(true);
  onScopeDispose(() => {
    alive.value = false;
  });
  return alive;
}
