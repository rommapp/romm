// focusRestoration (v2) — remembers each route's last focused tile so
// going back from a detail view (gallery, game detail, …) lands the
// user on the tile they clicked instead of the first cell.
//
// Why this exists: pad / key navigation flows feel broken when "back"
// resets focus to the top of the index. With this store, useGridNav /
// useWrapGridNav save the focused tile's `data-focus-key` on every
// focusin and, on mount, look it up to seed the autofocus target.
//
// Identifier: opaque string per consumer (`rom-{id}`, `platform-{id}`,
// `collection-{kind}-{id}`, …). Stable across renders — the composables
// match the saved key against any `[data-focus-key]` element in the
// view's root.
//
// Restoration is non-destructive: re-reading the same key keeps the
// value so back-and-forth navigation keeps landing on the same tile.
import { defineStore } from "pinia";

interface State {
  keys: Map<string, string>;
}

export default defineStore("v2FocusRestoration", {
  state: (): State => ({ keys: new Map() }),
  actions: {
    save(routeFullPath: string, focusKey: string) {
      if (!focusKey) return;
      this.keys.set(routeFullPath, focusKey);
    },
    restore(routeFullPath: string): string | null {
      return this.keys.get(routeFullPath) ?? null;
    },
    clear(routeFullPath: string) {
      this.keys.delete(routeFullPath);
    },
  },
});
