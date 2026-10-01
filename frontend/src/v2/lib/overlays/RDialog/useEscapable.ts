import { onBeforeUnmount, type Ref, watch } from "vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "./escapeStack";

/** Keep a popover on the escape stack while `isOpen`, so Escape and pad B
 *  close it before any overlay it sits in. Returns the stack entry. */
export function useEscapable(
  isOpen: Readonly<Ref<boolean>>,
  close: () => void,
  panel?: () => HTMLElement | null,
): EscapableEntry {
  const entry: EscapableEntry = { close, persistent: false, panel };

  watch(
    isOpen,
    (open) => {
      if (open) pushEscapable(entry);
      else popEscapable(entry);
    },
    { immediate: true },
  );
  onBeforeUnmount(() => popEscapable(entry));

  return entry;
}
