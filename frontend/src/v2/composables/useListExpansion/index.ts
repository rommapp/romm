// useListExpansion — one open detail panel at a time in a list-mode table.
//
// Every surface that renders `GameListRow` (the gallery shell, Settings →
// Missing games) needs the same two things: which row is open, and the height
// that row now takes, since the virtualiser reserves each row's slot up front.
// Keeping both here is what makes the two tables behave identically.
//
// The panel rolls open and shut like a blind, which only reads right if the
// reserved slot grows and shrinks with it — a panel animating inside a slot
// that already jumped to its full height just fades. So the height is animated
// here, and both the row's panel and the virtualiser read the same number.
import { onScopeDispose, ref } from "vue";
import {
  LIST_ROW_DETAIL_HEIGHT_PX,
  listRowHeight,
} from "@/v2/components/Gallery/listColumns";
import { useReducedMotion } from "@/v2/composables/useReducedMotion";
import { motion } from "@/v2/tokens";
import { tween } from "@/v2/utils/tween";

const DURATION_MS = parseInt(motion.med, 10);

export function useListExpansion() {
  const { enabled: reducedMotion } = useReducedMotion();
  /** The row painting a panel — set while it rolls shut, too. */
  const expandedPosition = ref<number | null>(null);
  /** How much of the panel is currently showing, in px. */
  const openHeight = ref(0);

  let cancelAnimation: (() => void) | null = null;

  function stopAnimation() {
    cancelAnimation?.();
    cancelAnimation = null;
  }

  function animateTo(target: number, onDone?: () => void) {
    stopAnimation();
    cancelAnimation = tween({
      from: openHeight.value,
      to: target,
      durationMs: reducedMotion.value ? 0 : DURATION_MS,
      onUpdate: (value) => (openHeight.value = value),
      onDone,
    });
  }

  function isExpanded(position: number | null | undefined): boolean {
    return position != null && expandedPosition.value === position;
  }

  /** Panel height for the row at `position` — 0 for every other row. */
  function detailHeight(position: number | null | undefined): number {
    return isExpanded(position) ? openHeight.value : 0;
  }

  function toggle(position: number) {
    if (isExpanded(position)) {
      animateTo(0, () => (expandedPosition.value = null));
      return;
    }
    expandedPosition.value = position;
    openHeight.value = 0;
    animateTo(LIST_ROW_DETAIL_HEIGHT_PX);
  }

  function collapse() {
    stopAnimation();
    expandedPosition.value = null;
    openHeight.value = 0;
  }

  /** Height of the row at `position`, however much panel is showing. */
  function rowHeight(position: number | null | undefined): number {
    return listRowHeight(detailHeight(position));
  }

  onScopeDispose(stopAnimation);

  return {
    isExpanded,
    detailHeight,
    toggle,
    collapse,
    rowHeight,
  };
}
