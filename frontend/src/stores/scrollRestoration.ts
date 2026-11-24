// Each gallery route's last page scroll, reapplied once the first window has
// loaded: the router's own restore runs before the rows have their height.
import { defineStore } from "pinia";

interface State {
  positions: Map<string, number>;
}

export default defineStore("v2ScrollRestoration", {
  state: (): State => ({ positions: new Map() }),
  actions: {
    save(routeFullPath: string, scrollTop: number) {
      // 0 is meaningful (top of list): only skip on negatives / NaN.
      if (!Number.isFinite(scrollTop) || scrollTop < 0) return;
      this.positions.set(routeFullPath, scrollTop);
    },
    restore(routeFullPath: string): number | null {
      return this.positions.get(routeFullPath) ?? null;
    },
    clear(routeFullPath: string) {
      this.positions.delete(routeFullPath);
    },
  },
});
