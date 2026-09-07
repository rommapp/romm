// Props for RCarousel. Kept in its own module (not inline in the SFC) because
// RCarousel is a generic component (`<T>`) — an inline `interface Props` leaks
// into the compiled default export as a private name (TS4082), and `export`
// isn't allowed inside `<script setup>`.
export interface RCarouselProps<TItem> {
  /** Active item index. */
  modelValue: number;
  /** Items array — the slot decides how each one is rendered. */
  items: readonly TItem[];
  /** Render as a viewport-filling overlay with scrim and close button. */
  fullscreen?: boolean;
  /** Wrap from last → first and first → last. */
  loop?: boolean;
  /** Show "n / total" counter. Defaults to true when `items.length > 1`. */
  showCounter?: boolean;
  /** Show prev/next arrows. Defaults to true when `items.length > 1`. */
  showArrows?: boolean;
  /** Show a thumbnail strip below the active item. */
  showThumbnails?: boolean;
  /** Localised label for the close button. */
  closeLabel?: string;
  /** Localised label for the prev button. */
  prevLabel?: string;
  /** Localised label for the next button. */
  nextLabel?: string;
  /** Accessibility label for the carousel region. */
  ariaLabel?: string;
}
