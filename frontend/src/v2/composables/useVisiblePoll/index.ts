// Calls `fn` every `intervalMs` while the tab is visible, and once as soon as
// it is shown again, so a backgrounded tab sends no requests nobody will see.
import {
  useDocumentVisibility,
  useIntervalFn,
  type Pausable,
} from "@vueuse/core";
import { watch } from "vue";

export function useVisiblePoll(
  fn: () => void,
  intervalMs: number,
  { immediate = true }: { immediate?: boolean } = {},
): Pausable {
  const visibility = useDocumentVisibility();
  const poll = useIntervalFn(
    () => {
      if (visibility.value === "visible") fn();
    },
    intervalMs,
    { immediate },
  );
  watch(visibility, (state) => {
    if (state === "visible" && poll.isActive.value) fn();
  });
  return poll;
}
