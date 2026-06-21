// Discriminated union describing every kind of row that can live inside a
// virtualised gallery scroller. The view turns this list into a single
// RVirtualScroller and renders per kind via a template switch.
//
// IMPORTANT — performance contract: row items are STRUCTURAL only. They
// know which positions they cover but they do NOT carry the actual ROM /
// skeleton data. The view template iterates positions inline and calls
// `store.getRomAt(p)` per slot. That keeps Vue's per-key reactivity
// granular: when a window resolves and a single position transitions
// from skeleton to ROM, only the affected row component re-renders —
// not the entire `virtualItems` array (which would be O(total/cols)
// rebuild and was the source of the scroll-freeze in earlier passes).

// `hero` (header) and `toolbar` are NOT virtual items — they live in
// `RVirtualScroller`'s `#prepend` and `#sticky` slots respectively, so
// the browser's compositor handles their layout (header scrolls with
// content, toolbar pins via native `position: sticky`). Keeping them
// out of the virtualised list avoids JS-driven scroll tracking and the
// jitter that came with it.
export type GalleryItem =
  | { kind: "letter-header"; key: string; letter: string }
  /** Grid layout — a virtualised slice of the column-masonry. A band owns
   * a contiguous run of positions distributed across the responsive
   * column count (shortest-column-first), so covers render at their
   * natural aspect ratio with no forced box. Columns reset per band: the
   * shortest-first balance levels each band's bottom edge, so the seam
   * between bands is barely visible while keeping the scroller's
   * per-item exact-offset model intact. The view renders one vertical
   * card stack per entry in `columns`. */
  | {
      kind: "masonry-band";
      key: string;
      /** Total pixel height of the band (tallest column + bottom gap).
       * Fed straight to RVirtualScroller's `getItemHeight`. */
      height: number;
      startPosition: number;
      endPosition: number; // exclusive
      /** Per visual column, the ordered positions assigned to it. Length
       * equals the active responsive column count. */
      columns: readonly (readonly number[])[];
      /** Letters covered by this band's position range (from server's
       * charIndex). Drives AlphaStrip spy highlight even when the band's
       * cards aren't loaded yet. */
      letters: readonly string[];
    }
  /** List layout — one virtual item per ROM. The view template reads
   * `position` and resolves the ROM (or skeleton) via `getRomAt`. The
   * sticky column header lives in the shell's prepend, not as a virtual
   * item, so it can stay pinned below the toolbar regardless of scroll. */
  | {
      kind: "list-row";
      key: string;
      position: number;
      /** First letter of this position (from charIndex / letterRanges).
       * Used by AlphaStrip's scroll-spy in list mode. */
      letter: string;
    }
  /** List-layout placeholder painted while the very first metadata
   * bootstrap is in flight (`total` is still 0). Same height as a real
   * `list-row` so the scroller doesn't reflow once `total` resolves. */
  | { kind: "skeleton-list-row"; key: string; index: number }
  | { kind: "load-more"; key: string; remaining: number; loading: boolean }
  | { kind: "empty"; key: string; message: string }
  | { kind: "skeleton-row"; key: string; index: number };

export type GalleryItemKind = GalleryItem["kind"];
