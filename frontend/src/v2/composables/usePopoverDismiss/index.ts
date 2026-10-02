import { onBeforeUnmount, type Ref, watch } from "vue";
import { useEscapable } from "@/v2/composables/useEscapable";
import { isInsideEscapableAbove } from "@/v2/lib/overlays/RDialog/escapeStack";

export interface PopoverDismissOptions {
  /** The element that opens the popover; presses on it are not outside. */
  reference: () => Element | null;
  /** The popover surface. Read lazily, since it mounts only while open. */
  panel: () => HTMLElement | null;
  /** Escape / pad B handler, when it should do more than `close`. */
  onEscape?: () => void;
}

/** Close a popover on Escape, pad B, or a press outside it. A press inside
 *  an overlay opened above it (a nested menu or picker) is not outside. */
export function usePopoverDismiss(
  isOpen: Readonly<Ref<boolean>>,
  close: () => void,
  { reference, panel, onEscape }: PopoverDismissOptions,
): void {
  const entry = useEscapable(isOpen, onEscape ?? close, panel);

  function onDocPointerDown(evt: PointerEvent) {
    if (!isOpen.value) return;
    const target = evt.target as Node | null;
    if (!target) return;
    if (reference()?.contains(target)) return;
    if (panel()?.contains(target)) return;
    if (isInsideEscapableAbove(entry, target)) return;
    close();
  }

  function detach() {
    document.removeEventListener("pointerdown", onDocPointerDown, true);
  }

  watch(
    isOpen,
    (open) => {
      if (open)
        document.addEventListener("pointerdown", onDocPointerDown, true);
      else detach();
    },
    { immediate: true },
  );
  onBeforeUnmount(detach);
}
