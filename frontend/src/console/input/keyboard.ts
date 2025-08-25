import { InputBus } from "./bus";
import { defaultInputConfig } from "./config";

export function attachKeyboard(bus: InputBus) {
  const onKey = (e: KeyboardEvent) => {
    const target = e.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable)
    ) {
      return;
    }
    const action = defaultInputConfig.keyMap[e.key];
    if (!action) return;
    const handled = bus.dispatch(action);
    if (handled) e.preventDefault();
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}
