// scrollRestoration (v2) — remembers each route's last scrollTop on the
// gallery views' custom scroll containers (RVirtualScroller's
// containerEl).
//
// Why this exists: Vue Router's built-in `scrollBehavior` only restores
// `window` scroll. Gallery views use a child scroller — going back from
// GameDetails would otherwise dump the user at the top instead of where
// they left off. This store captures `scrollTop` per fullPath; views
// save on `onBeforeRouteLeave` and read in `onMounted` after the first
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
      // 0 is meaningful (top of list) — only skip on negatives / NaN.
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
