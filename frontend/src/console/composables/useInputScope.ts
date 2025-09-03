import { inject, onMounted, onUnmounted } from "vue";
import type { InputListener } from "@/console/input/actions";
import { InputBus, InputBusSymbol } from "@/console/input/bus";

export function useInputScope() {
  const bus = inject<InputBus>(InputBusSymbol);

  if (!bus) {
    throw new Error(
      "useInputScope must be used within a component that provides InputBus",
    );
  }

  let unsubscribe: (() => void) | null = null;

  onMounted(() => {
    unsubscribe = bus.pushScope();
  });

  onUnmounted(() => {
    if (unsubscribe) {
      unsubscribe();
      unsubscribe = null;
    }
  });

  const subscribe = (listener: InputListener) => {
    return bus.subscribe(listener);
  };

  return {
    bus,
    subscribe,
  };
}
