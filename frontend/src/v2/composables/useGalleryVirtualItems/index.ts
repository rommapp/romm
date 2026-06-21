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
import {
  computed,
  toValue,
  type ComputedRef,
  type MaybeRefOrGetter,
  type Ref,
} from "vue";
import { LIST_ROW_HEIGHT_PX } from "@/v2/components/Gallery/listColumns";
import type { GroupByMode, LayoutMode } from "../useGalleryMode";
import type { GalleryItem } from "./types";

export type { GalleryItem, GalleryItemKind } from "./types";

// Row chrome below the cover art added to the cover box height to get a
// grid row's total height: 7px gap + 16px label + 18px bottom padding = 41.
const ROW_CHROME_PX = 41;
// Reference card-art width the row height is derived from when the caller
// doesn't pass one (md gallery card). Height = width / ratio + chrome.
const REFERENCE_COVER_WIDTH_PX = 158;
// Box-art default — matches v1's `getAspectRatio` for `cover_path`.
const DEFAULT_COVER_RATIO = 2 / 3;

// ── Column-masonry geometry ─────────────────────────────────────────
// A card's full height is its cover box (`cardWidth / ratio`, exact —
// the card is fixed-width so the cover renders at exactly that height)
// plus the label chrome below it (7px margin-top + 16px label line).
const CARD_LABEL_CHROME_PX = 23;
// Vertical gap between stacked cards in a column (matches the grid row
// gap the uniform layout used). Also the gap below each band.
const CARD_V_GAP_PX = 18;
// Target number of visual rows per virtualised band. Bands are the unit
// the scroller virtualises; columns reset at each boundary. Shortest-
// column-first balancing levels a band's bottom edge, so this only trades
// seam frequency against how many cards mount per band — not visual
// quality. ~8 rows keeps the mounted-card count near the old uniform grid.
const BAND_ROWS = 8;

/** Full pixel height of a single masonry card (cover + label chrome). */
function masonryCardHeight(ratio: number, cardWidth: number): number {
  const r = ratio > 0 ? ratio : DEFAULT_COVER_RATIO;
  return cardWidth / r + CARD_LABEL_CHROME_PX;
}

interface BandLayout {
  /** Per visual column, the ordered positions assigned to it. */
  columns: number[][];
  /** Tallest column height in px (before the band's bottom gap). */
  height: number;
}

/** Distribute a contiguous run of positions across `cols` columns using
 *  shortest-column-first placement (classic balanced masonry). Returns the
 *  per-column position lists and the band's content height. Pure — exported
 *  for unit tests. */
export function layoutMasonryBand(
  positions: readonly number[],
  cols: number,
  cardWidth: number,
  ratioAt: (position: number) => number,
): BandLayout {
  const n = Math.max(1, cols);
  const colHeights = new Array<number>(n).fill(0);
  const columns: number[][] = Array.from({ length: n }, () => []);
  for (const p of positions) {
    // Shortest column wins; ties go to the leftmost for stable output.
    let c = 0;
    for (let i = 1; i < n; i++) {
      if (colHeights[i] < colHeights[c]) c = i;
    }
    if (columns[c].length > 0) colHeights[c] += CARD_V_GAP_PX;
    colHeights[c] += masonryCardHeight(ratioAt(p), cardWidth);
    columns[c].push(p);
  }
  let height = 0;
  for (const h of colHeights) if (h > height) height = h;
  return { columns, height };
}

// Fixed heights for the item kinds that DON'T depend on the boxart
// aspect ratio. Row / skeleton-row are computed per-style — see
// `getItemHeight`. Values match the rendered geometry in the gallery
// views' CSS:
//   * letter-header: 20px top + 16px text + 12px bottom = 48 (→ 56 for air).
//   * load-more / empty: rendered button / centered text.
//   * list-row / skeleton-list-row: token-derived `LIST_ROW_HEIGHT_PX`.
const FIXED_HEIGHT_BY_KIND: Partial<Record<GalleryItem["kind"], number>> = {
  "letter-header": 56,
  "list-row": LIST_ROW_HEIGHT_PX,
  "skeleton-list-row": LIST_ROW_HEIGHT_PX,
  "load-more": 80,
  empty: 240,
};

/** Total height of a grid row for a cover aspect ratio + card width. The
 *  cover box height is `width / ratio` (matches the card's `aspect-ratio`
 *  rule); chrome is the label + gaps below it. Exported for unit tests. */
export function galleryRowHeight(
  ratio: number = DEFAULT_COVER_RATIO,
  cardWidth: number = REFERENCE_COVER_WIDTH_PX,
): number {
  return Math.round(cardWidth / ratio) + ROW_CHROME_PX;
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
  /** Fallback cover aspect ratio (width / height) used for the bootstrap
   *  skeleton rows, before per-position ratios are known. Defaults to
   *  box-art 2/3. */
  coverRatio?: MaybeRefOrGetter<number>;
  /** Per-position natural cover aspect ratio (width / height), aligned to
   *  the gallery's position order. `null` entries fall back to the default
   *  box-art ratio. Drives the column-masonry layout so every card sits at
   *  its true ratio and the band offsets are exact before covers stream
   *  in. */
  coverRatios?: MaybeRefOrGetter<readonly (number | null)[]>;
  /** Card-art width used to derive card / band heights (match the value
   *  fed to `useResponsiveColumns`). Defaults to the md card (158px). */
  cardWidth?: MaybeRefOrGetter<number>;
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

  const cardWidthPx = () =>
    opts.cardWidth != null ? toValue(opts.cardWidth) : REFERENCE_COVER_WIDTH_PX;

  // Uniform skeleton-row height for the bootstrap phase, before any
  // per-position ratio is known — falls back to the box-art shape.
  const skeletonRowHeightPx = computed(() =>
    galleryRowHeight(
      opts.coverRatio != null ? toValue(opts.coverRatio) : DEFAULT_COVER_RATIO,
      cardWidthPx(),
    ),
  );

  // Signature matches RVirtualScroller's `getItemHeight` prop (which uses
  // `unknown` because the primitive is generic). Masonry bands carry their
  // own exact height; skeleton rows use the uniform fallback; every other
  // kind is fixed.
  function getItemHeight(item: unknown): number {
    const it = item as GalleryItem;
    if (it.kind === "masonry-band") return it.height;
    if (it.kind === "skeleton-row") return skeletonRowHeightPx.value;
    return FIXED_HEIGHT_BY_KIND[it.kind] ?? 0;
  }

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
    const cardWidth = cardWidthPx();
    const bandSize = cols * BAND_ROWS;
    const ratios = opts.coverRatios != null ? toValue(opts.coverRatios) : [];
    const ratioAt = (position: number): number => {
      const r = ratios[position];
      return r != null && r > 0 ? r : DEFAULT_COVER_RATIO;
    };

    // Emit the masonry bands covering a contiguous position range. Each
    // band runs its own shortest-column-first layout (columns reset at the
    // boundary) so it carries an exact pixel height for the scroller.
    const pushBands = (
      start: number,
      end: number,
      keyPrefix: string,
      bandLetters: (s: number, e: number) => readonly string[],
    ) => {
      for (let bandStart = start; bandStart < end; bandStart += bandSize) {
        const bandEnd = Math.min(bandStart + bandSize, end);
        const positions: number[] = [];
        for (let p = bandStart; p < bandEnd; p++) positions.push(p);
        const { columns, height } = layoutMasonryBand(
          positions,
          cols,
          cardWidth,
          ratioAt,
        );
        items.push({
          kind: "masonry-band",
          key: `${keyPrefix}-${bandStart}`,
          height: height + CARD_V_GAP_PX,
          startPosition: bandStart,
          endPosition: bandEnd,
          columns,
          letters: bandLetters(bandStart, bandEnd),
        });
      }
    };

    if (opts.groupBy.value === "letter") {
      // Group by letter — each letter section gets a header followed by its
      // own masonry bands (columns restart at the letter's first position,
      // so a letter never shares a visual column run with another).
      for (const range of ranges) {
        items.push({
          kind: "letter-header",
          key: `lh-${range.letter}`,
          letter: range.letter,
        });
        pushBands(range.start, range.end, `band-${range.letter}`, () => [
          range.letter,
        ]);
      }
    } else {
      // Flat — bands aligned to absolute positions from 0.
      pushBands(0, total, "band-flat", (s, e) => lettersInRange(ranges, s, e));
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
      // Flat mode — bands tile [0, total) by `bandSize` from 0, so the band
      // holding a letter's first position is a direct index offset from the
      // first band item.
      let firstBandIdx = -1;
      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === "masonry-band") {
          firstBandIdx = i;
          break;
        }
      }
      if (firstBandIdx >= 0) {
        const cols = Math.max(1, opts.columns.value);
        const bandSize = cols * BAND_ROWS;
        for (const range of letterRanges.value) {
          if (map.has(range.letter)) continue;
          map.set(
            range.letter,
            firstBandIdx + Math.floor(range.start / bandSize),
          );
        }
      }
    }

    return map;
  });

  return {
    virtualItems,
    letterToIndex,
    availableLetters,
    getItemHeight,
    ALPHABET,
  };
}
