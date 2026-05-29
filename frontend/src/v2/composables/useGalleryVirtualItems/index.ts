// useGalleryVirtualItems — turns the gallery's structural state (mode,
// total, charIndex, columns) into a flat list of body `GalleryItem`s
// that an RVirtualScroller can render with one slot per kind.
//
// Header and toolbar are NOT in this list — they live in the
// scroller's `#prepend` and `#sticky` slots so `position: sticky`
// handles pinning natively (no JS scroll tracking, no jitter).
//
// Performance contract: this composable is STRUCTURAL — it only
// depends on layout / groupBy / total / charIndex / columns /
// loadingInitial. It does NOT read the loaded ROMs (`byPosition`).
// Per-row slot data is resolved by the view at render time via
// `store.getRomAt(position)`, which scopes Vue's reactivity to the
// specific row that holds the resolved position. A window fetch that
// lands 72 ROMs only re-renders up to ⌈72/cols⌉ rows, not the entire
// virtualItems array.
//
// AlphaStrip integration is index-based: `letterToIndex` maps each
// available letter to the index of its first item in `virtualItems`,
// fed straight into `RVirtualScroller.scrollToIndex(idx, { stickyOffset })`.
// `availableLetters` derives from the server's `charIndex` so every
// letter that exists in the gallery is clickable, even if its window
// hasn't been fetched yet.
import { computed, type ComputedRef, type Ref } from "vue";
import { LIST_ROW_HEIGHT_PX } from "@/v2/components/Gallery/listColumns";
import type { GroupByMode, LayoutMode } from "../useGalleryMode";
import type { GalleryItem } from "./types";

export type { GalleryItem, GalleryItemKind } from "./types";

// Height table per item kind. Drives the virtualiser's exact-offset
// math, so AlphaStrip jumps land precisely on target rows. Values match
// the rendered geometry in the gallery views' CSS:
//   * row / skeleton-row: 213px cover + 7px gap + 16px label + 18px
//     bottom-padding = 254.
//   * letter-header: 20px top + 16px text + 12px bottom = 48 (rounded
//     up to 56 for breathing room).
//   * load-more / empty: matches the rendered button / centered text.
//   * list-row / skeleton-list-row: sourced from `LIST_ROW_HEIGHT_PX`
//     (token-derived) so changing the list-row height in tokens flows
//     through here without drifting from the rendered CSS.
const HEIGHT_BY_KIND: Record<GalleryItem["kind"], number> = {
  "letter-header": 56,
  row: 254,
  "skeleton-row": 254,
  "list-row": LIST_ROW_HEIGHT_PX,
  "skeleton-list-row": LIST_ROW_HEIGHT_PX,
  "load-more": 80,
  empty: 240,
};

// Signature matches RVirtualScroller's `getItemHeight` prop (which uses
// `unknown` for items because the primitive is generic). Internally
// narrows back to GalleryItem — the caller is always passing items
// produced by `useGalleryVirtualItems`, so the cast is safe.
export function galleryItemHeight(item: unknown): number {
  return HEIGHT_BY_KIND[(item as GalleryItem).kind];
}

interface Options {
  layout: Ref<LayoutMode> | ComputedRef<LayoutMode>;
  groupBy: Ref<GroupByMode> | ComputedRef<GroupByMode>;
  /** Total count of ROMs in the active gallery (server-provided). */
  total: Ref<number> | ComputedRef<number>;
  /** Letter → first-position map from the server. Backend ships letters
   * lowercase / digits — `availableLetters` and the row letter sets
   * normalise to AlphaStrip's bucket shape. */
  charIndex: Ref<Record<string, number>> | ComputedRef<Record<string, number>>;
  /** Current column count for grid modes (responsive). */
  columns: Ref<number> | ComputedRef<number>;
  /** True while the very first window is in flight (no `total` yet). */
  loadingInitial: ComputedRef<boolean>;
  /** Empty-state message used when the page resolves with zero results. */
  emptyMessage: Ref<string> | ComputedRef<string>;
  /** "Not found" — overrides every body kind with a single empty row. */
  notFound?: Ref<boolean> | ComputedRef<boolean>;
  /** Override the not-found message (defaults to emptyMessage). */
  notFoundMessage?: Ref<string> | ComputedRef<string>;
  /** Skeleton row count while loading the first window. */
  skeletonRowCount?: number;
}

const ALPHABET = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ@".split("");

function normaliseBackendLetter(raw: string): string {
  if (!raw) return "@";
  const c = raw.charAt(0).toUpperCase();
  if (/[A-Z]/.test(c)) return c;
  if (/[0-9]/.test(c)) return "#";
  return "@";
}

interface LetterRange {
  letter: string;
  start: number;
  end: number; // exclusive
}

function buildLetterRanges(
  charIndex: Record<string, number>,
  total: number,
): LetterRange[] {
  const entries = Object.entries(charIndex)
    .map(([letter, off]) => [normaliseBackendLetter(letter), off] as const)
    .sort((a, b) => a[1] - b[1]);
  const ranges: LetterRange[] = [];
  for (let i = 0; i < entries.length; i++) {
    const [letter, start] = entries[i];
    const end = entries[i + 1]?.[1] ?? total;
    // Backend may collapse multiple raw letters into "#" (digits, etc.) —
    // merge into the previous range rather than emit duplicates.
    const last = ranges[ranges.length - 1];
    if (last && last.letter === letter) {
      last.end = end;
      continue;
    }
    ranges.push({ letter, start, end });
  }
  return ranges;
}

function lettersInRange(
  ranges: LetterRange[],
  startPos: number,
  endPos: number,
): string[] {
  const out: string[] = [];
  for (const r of ranges) {
    if (r.end > startPos && r.start < endPos) out.push(r.letter);
  }
  return out;
}

export function useGalleryVirtualItems(opts: Options) {
  const skeletonRows = opts.skeletonRowCount ?? 4;

  const letterRanges = computed<LetterRange[]>(() =>
    buildLetterRanges(opts.charIndex.value, opts.total.value),
  );

  const virtualItems = computed<GalleryItem[]>(() => {
    const items: GalleryItem[] = [];

    if (opts.notFound?.value) {
      items.push({
        kind: "empty",
        key: "not-found",
        message: opts.notFoundMessage?.value ?? opts.emptyMessage.value,
      });
      return items;
    }

    // List layout — one virtual item per ROM position. The view template
    // resolves each row via `getRomAt(position)` and renders skeleton vs
    // real inside the same kind. Group-by-letter in list mode is
    // deferred (see CLAUDE.md §X — list-mode MVP first).
    if (opts.layout.value === "list") {
      if (opts.loadingInitial.value && opts.total.value === 0) {
        // Bootstrap phase — paint placeholder rows so the scroller has a
        // shape while metadata is in flight. Reasonable count to fill a
        // typical viewport without committing to a fixed number.
        const skeletonListRows = Math.max(skeletonRows * 4, 12);
        for (let i = 0; i < skeletonListRows; i++) {
          items.push({
            kind: "skeleton-list-row",
            key: `sk-list-${i}`,
            index: i,
          });
        }
        return items;
      }
      if (opts.total.value === 0) {
        items.push({
          kind: "empty",
          key: "empty",
          message: opts.emptyMessage.value,
        });
        return items;
      }
      const ranges = letterRanges.value;
      const total = opts.total.value;
      // Pre-compute a position → letter lookup so each list-row knows
      // which letter it belongs to (drives AlphaStrip's scroll-spy).
      // Walking `ranges` once (sorted by start) is O(total) — acceptable
      // because virtualItems already iterates `total`.
      let rangeIdx = 0;
      for (let p = 0; p < total; p++) {
        while (
          rangeIdx + 1 < ranges.length &&
          p >= ranges[rangeIdx + 1].start
        ) {
          rangeIdx++;
        }
        const letter = ranges[rangeIdx]?.letter ?? "#";
        items.push({
          kind: "list-row",
          key: `lr-${p}`,
          position: p,
          letter,
        });
      }
      return items;
    }

    // Grid + first-window-loading — show skeleton rows until the server
    // tells us `total` and `charIndex`.
    if (opts.loadingInitial.value && opts.total.value === 0) {
      for (let i = 0; i < skeletonRows; i++) {
        items.push({ kind: "skeleton-row", key: `skel-${i}`, index: i });
      }
      return items;
    }

    if (opts.total.value === 0) {
      items.push({
        kind: "empty",
        key: "empty",
        message: opts.emptyMessage.value,
      });
      return items;
    }

    const cols = Math.max(1, opts.columns.value);
    const total = opts.total.value;
    const ranges = letterRanges.value;

    if (opts.groupBy.value === "letter") {
      // Group by letter — each letter section gets a header followed by
      // its own row chunks (rows always restart at the letter's first
      // position, so a letter never shares a visual row with another).
      for (const range of ranges) {
        items.push({
          kind: "letter-header",
          key: `lh-${range.letter}`,
          letter: range.letter,
        });
        const rowsInGroup = Math.ceil((range.end - range.start) / cols);
        for (let r = 0; r < rowsInGroup; r++) {
          const rowStart = range.start + r * cols;
          const rowEnd = Math.min(rowStart + cols, range.end);
          items.push({
            kind: "row",
            key: `row-${range.letter}-${r}`,
            rowIndex: r,
            startPosition: rowStart,
            endPosition: rowEnd,
            letters: [range.letter],
          });
        }
      }
    } else {
      // Flat — rows are aligned to absolute positions.
      const totalRows = Math.ceil(total / cols);
      for (let r = 0; r < totalRows; r++) {
        const rowStart = r * cols;
        const rowEnd = Math.min(rowStart + cols, total);
        items.push({
          kind: "row",
          key: `row-flat-${r}`,
          rowIndex: r,
          startPosition: rowStart,
          endPosition: rowEnd,
          letters: lettersInRange(ranges, rowStart, rowEnd),
        });
      }
    }

    return items;
  });

  // AlphaStrip available letters — every letter in the server's charIndex,
  // independent of which windows are currently loaded.
  const availableLetters = computed<Set<string>>(() => {
    const set = new Set<string>();
    for (const r of letterRanges.value) set.add(r.letter);
    return set;
  });

  // letter → index in virtualItems for scroll-to-letter.
  const letterToIndex = computed<Map<string, number>>(() => {
    const map = new Map<string, number>();
    const items = virtualItems.value;

    // List layout — one virtual item per position. Walk once and pin
    // each letter to its first list-row index. Bootstrap phase paints
    // skeleton-list-rows that aren't tied to a letter, so the map is
    // empty until `total` resolves — same pattern as grid.
    if (opts.layout.value === "list") {
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it.kind === "list-row" && !map.has(it.letter)) {
          map.set(it.letter, i);
        }
      }
      return map;
    }

    // Pass 1 — grouped mode: letter-header anchors are exact.
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (it.kind === "letter-header" && !map.has(it.letter)) {
        map.set(it.letter, i);
      }
    }

    if (opts.groupBy.value !== "letter") {
      // Flat mode — for each letter range, jump to the row that holds
      // its first position.
      let firstRowIdx = -1;
      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === "row") {
          firstRowIdx = i;
          break;
        }
      }
      if (firstRowIdx >= 0) {
        const cols = Math.max(1, opts.columns.value);
        for (const range of letterRanges.value) {
          if (map.has(range.letter)) continue;
          map.set(range.letter, firstRowIdx + Math.floor(range.start / cols));
        }
      }
    }

    return map;
  });

  return {
    virtualItems,
    letterToIndex,
    availableLetters,
    ALPHABET,
  };
}
