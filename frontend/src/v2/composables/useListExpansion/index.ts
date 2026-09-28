// useListExpansion: one open detail panel at a time in a list-mode table.
//
// The panel rolls open like a blind, which only reads right if the rows below
// it move with it. They do, but not by animating the row's slot: the offset
// table an open row belongs to is O(n) to rebuild, so a per-frame height would
// rebuild it on every frame of the roll. Instead the table reserves the
// settled height from the moment the row opens, and `shiftPx` carries the
// difference for the frames in between (see RVirtualScroller's `offsetShift`).
import { computed, onScopeDispose, ref } from "vue";
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
  /** The row painting a panel, set while it rolls shut too. */
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

  /** Panel px to paint on the row at `position`, mid-roll included. */
  function panelHeight(position: number | null | undefined): number {
    return isExpanded(position) ? openHeight.value : 0;
  }

  /** What the open row's panel settles at, which is what the offset table
   *  reserves from the moment it opens. */
  function settledPanelHeight(position: number | null | undefined): number {
    return isExpanded(position) ? LIST_ROW_DETAIL_HEIGHT_PX : 0;
  }

  /** Settled height of the row at `position`, panel included when open. */
  function rowHeight(position: number | null | undefined): number {
    return listRowHeight(settledPanelHeight(position));
  }

  /** How far the rows below the open one still are from their settled place:
   *  0 at rest, down to -LIST_ROW_DETAIL_HEIGHT_PX the moment it opens. */
  const shiftPx = computed(() =>
    expandedPosition.value == null
      ? 0
      : openHeight.value - LIST_ROW_DETAIL_HEIGHT_PX,
  );

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

  onScopeDispose(stopAnimation);

  return {
    expandedPosition,
    shiftPx,
    isExpanded,
    panelHeight,
    settledPanelHeight,
    rowHeight,
    toggle,
    collapse,
  };
}
