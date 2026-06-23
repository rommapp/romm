// v2GallerySelection — multi-select state for the gallery views
// (Platform / Search / Collection). v2-only; v1's `stores/roms.ts`
// still owns the legacy selection fields and is the canonical store
// for v1 — v2 starts fresh so the existing surface can be improved
// without bending the v1 contract.
//
// Selection model:
//   - `selected: Map<number, SimpleRom>` — the source of truth, keyed
//     by rom id. We keep the full `SimpleRom` (not just the id) so
//     the SelectionBar's bulk actions can dispatch dialog events and
//     API calls without re-resolving against the sparse gallery
//     cache (`galleryRoms.byPosition`), which may have evicted the
//     rom by the time the user runs the action. Memory is bounded
//     by the size of the selection — well within the gallery's
//     working set.
//   - `lastSelectedPosition: number | null` — anchor for shift-range
//     selection. Stored as a *position* in the sparse gallery (matches
//     `galleryRoms.byPosition` keys) rather than an index into a dense
//     array, because v2's gallery is virtualised + sparse.
//   - `enabled` getter — true when at least one ROM is selected. The
//     "selection mode" is implicit (no separate flag) — first toggle
//     enters it, `clear()` exits it. Simpler than v1's
//     `selectingRoms: boolean` toggle, and matches the user-facing
//     expectation: "I am selecting iff I have selections."
//
// Scope:
//   - Selection is *per-gallery-view*. The store is global but call
//     sites (`GalleryShell`) clear on route change / context switch.
//     We don't clear inside the store itself — switching from Search
//     to a platform should drop the selection, but we let the view
//     decide so an in-page filter change can preserve it.
import { defineStore } from "pinia";
import type { SimpleRom } from "@/stores/roms";

interface State {
  selected: Map<number, SimpleRom>;
  /** Position (key in `galleryRoms.byPosition`) of the last toggled
   * ROM. Used as the anchor for shift-range selection. `null` means
   * no anchor yet (next shift-click acts as a single toggle). */
  lastSelectedPosition: number | null;
}

const defaults = (): State => ({
  selected: new Map<number, SimpleRom>(),
  lastSelectedPosition: null,
});

export default defineStore("v2GallerySelection", {
  state: defaults,

  getters: {
    /** True when the gallery is in "selection mode" — at least one
     * ROM is selected. Drives card/row visual affordances (checkbox
     * always visible) and the SelectionBar's open state. */
    enabled: (state) => state.selected.size > 0,
    /** Convenience for the SelectionBar's "N selected" label. */
    count: (state) => state.selected.size,
    /** Snapshot of the selected ROMs as an array — what the
     *  SelectionBar passes to dialog events / bulk APIs. Built on
     *  demand from the Map so callers always get a fresh array. */
    roms: (state): SimpleRom[] => Array.from(state.selected.values()),
    /** Snapshot of selected IDs — preferred when only IDs are
     *  needed (collection add/remove API takes id[]). */
    ids: (state): number[] => Array.from(state.selected.keys()),
  },

  actions: {
    isSelected(id: number): boolean {
      return this.selected.has(id);
    },

    /** Toggle a single ROM. Updates the range anchor unconditionally
     * — even when removing, so the next shift-click extends from the
     * just-clicked card (matches the de-facto behaviour of file
     * managers / mail clients). */
    toggle(rom: SimpleRom, position: number) {
      const next = new Map(this.selected);
      if (next.has(rom.id)) {
        next.delete(rom.id);
      } else {
        next.set(rom.id, rom);
      }
      this.selected = next;
      this.lastSelectedPosition = position;
    },

    /** Range selection from `lastSelectedPosition` to `position`,
     * inclusive. Resolves positions through `getRomAt` (provided by
     * the caller, typically `galleryRoms.getRomAt`) — positions that
     * aren't loaded yet are skipped. The range either adds every ROM
     * to the selection or removes every ROM, picked by the state of
     * the *target* position (matches v1: clicking a selected end-of-
     * range with shift extends the unselection). */
    toggleRange(position: number, getRomAt: (p: number) => SimpleRom | null) {
      const anchor = this.lastSelectedPosition;
      if (anchor === null || anchor === position) {
        const rom = getRomAt(position);
        if (rom) this.toggle(rom, position);
        return;
      }
      const [from, to] =
        anchor < position ? [anchor, position] : [position, anchor];
      // Direction of the range action: if the *target* is currently
      // selected, the user is shrinking the selection (deselect
      // range); otherwise extending it (select range).
      const targetRom = getRomAt(position);
      const removing = targetRom ? this.selected.has(targetRom.id) : false;
      const next = new Map(this.selected);
      for (let p = from; p <= to; p++) {
        const rom = getRomAt(p);
        if (!rom) continue;
        if (removing) next.delete(rom.id);
        else next.set(rom.id, rom);
      }
      this.selected = next;
      this.lastSelectedPosition = position;
    },

    /** Add every currently-loaded ROM in the gallery to the
     * selection. v2 galleries are sparse (only fetched windows are
     * present in `byPosition`), so this is "select all loaded" — not
     * "select all in the entire filtered set". Matches v1's UX (its
     * select-all also only touched ROMs already in memory) without
     * the perf cost of fetching every page upfront. */
    selectAllLoaded(loadedRoms: Iterable<SimpleRom>) {
      const next = new Map(this.selected);
      for (const rom of loadedRoms) next.set(rom.id, rom);
      this.selected = next;
    },

    /** Replace the selection with exactly the given ROMs. Used by
     * the SelectionBar's "select all visible" affordance when we want
     * to scope to a specific window (e.g., the current viewport). */
    setSelection(roms: Iterable<SimpleRom>) {
      this.selected = new Map(Array.from(roms, (r) => [r.id, r] as const));
    },

    /** Drop the selection and anchor. Bound to Esc, the SelectionBar
     * clear button, and view route-leave. */
    clear() {
      if (this.selected.size === 0 && this.lastSelectedPosition === null) {
        return;
      }
      this.selected = new Map<number, SimpleRom>();
      this.lastSelectedPosition = null;
    },

    /** Drop a subset by ID — used when a bulk action mutates only
     * part of the selection (e.g. delete-from-disk against a subset). */
    removeIds(ids: Iterable<number>) {
      const next = new Map(this.selected);
      for (const id of ids) next.delete(id);
      this.selected = next;
    },
  },
});
