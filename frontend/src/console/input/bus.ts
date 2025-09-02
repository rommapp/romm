import { sfxForAction, playSfx } from "../utils/sfx";
import type { InputAction, InputListener } from "./actions";

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
    for (let i = this.scopes.length - 1; i >= 0; i--) {
      const scope = this.scopes[i];
      for (const listener of scope) {
        const handled = listener(action);
        if (handled) {
          const kind = sfxForAction(action);
          if (kind) playSfx(kind);
          return true;
        }
      }
    }

    for (const listener of this.globalShortcuts) {
      const handled = listener(action);
      if (handled) {
        const kind = sfxForAction(action);
        if (kind) playSfx(kind);
        return true;
      }
    }

    return false;
  }
}

export const InputBusSymbol = Symbol("InputBus");
