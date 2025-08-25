import { inject, onMounted, onUnmounted } from "vue";
import { InputBus, InputBusSymbol } from "@/console/input/bus";
import type { InputListener } from "@/console/input/actions";

export function useInputScope() {
  const bus = inject<InputBus>(InputBusSymbol)!;
  let pop: (() => void) | null = null;
  onMounted(() => {
    pop = bus.pushScope();
  });
  onUnmounted(() => {
    pop?.();
    pop = null;
  });

  const on = (listener: InputListener) => bus.subscribe(listener);
  return { bus, on };
}
