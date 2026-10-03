// Subscribes to the injected app emitter and unsubscribes when the owning
// scope is disposed. Call it from `setup`: the emitter comes from `inject`.
import type { Emitter, Handler } from "mitt";
import { inject, onScopeDispose } from "vue";
import type { Events } from "@/types/emitter";

export interface EmitterEventHandle {
  /** Unsubscribe before the scope ends; idempotent. */
  stop: () => void;
}

export function useEmitterEvent<K extends keyof Events>(
  event: K,
  handler: Handler<Events[K]>,
): EmitterEventHandle {
  const emitter = inject<Emitter<Events>>("emitter");
  // eslint-disable-next-line no-restricted-syntax -- the one sanctioned subscription
  emitter?.on(event, handler);

  let stopped = false;
  const stop = () => {
    if (stopped) return;
    stopped = true;
    emitter?.off(event, handler);
  };

  onScopeDispose(stop);

  return { stop };
}
