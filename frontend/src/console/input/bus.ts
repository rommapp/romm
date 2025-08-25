import type { InputAction, InputListener } from "./actions";
import { sfxForAction, playSfx } from "../utils/sfx";

export class InputBus {
  private scopes: Array<Set<InputListener>> = [];
  private globalShortcuts: Set<InputListener> = new Set();

  pushScope(): () => void {
    const set = new Set<InputListener>();
    this.scopes.push(set);
    return () => this.popScope(set);
  }

  private popScope(scope: Set<InputListener>) {
    const idx = this.scopes.lastIndexOf(scope);
    if (idx >= 0) this.scopes.splice(idx, 1);
  }

  subscribe(listener: InputListener): () => void {
    const top = this.scopes[this.scopes.length - 1];
    if (!top) throw new Error("No active input scope. Call pushScope() first.");
    top.add(listener);
    return () => top.delete(listener);
  }

  subscribeGlobal(listener: InputListener): () => void {
    this.globalShortcuts.add(listener);
    return () => this.globalShortcuts.delete(listener);
  }

  dispatch(action: InputAction): boolean {
    this.scopes.forEach((scope) => {
      scope.forEach((listener) => {
        const handled = listener(action);
        if (handled) {
          const kind = sfxForAction(action);
          if (kind) playSfx(kind);
          return true;
        }
      });
    });
    this.globalShortcuts.forEach((listener) => {
      const handled = listener(action);
      if (handled) {
        const kind = sfxForAction(action);
        if (kind) playSfx(kind);
        return true;
      }
    });
    return false;
  }
}

export const InputBusSymbol = Symbol("InputBus");
