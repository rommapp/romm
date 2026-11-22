// scrollRestoration (v2): remembers each gallery route's last page scroll.
//
// Why this exists: Vue Router's `scrollBehavior` restores the offset as soon
// as the route renders, before a gallery's virtualised rows have their full
// height, so the browser clamps it short. This store captures the offset per
// fullPath; views save on `onBeforeRouteLeave` and reapply it once the first
// window has resolved.
//
// Restoration is non-destructive: re-reading the same key keeps the
// value so a user that navigates away and back-and-forth keeps landing
// at the last saved position.
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
