import { useTimeoutFn } from "@vueuse/core";
import { type Ref, ref, watch } from "vue";

/** A search box bound to a store term, debounced one way and immediate the
 *  other, so a term set by navigation shows up in the box. */
export function useDebouncedSearch(term: Ref<string | null>, delayMs = 300) {
  const input = ref(term.value ?? "");

  const commit = useTimeoutFn(
    (value: string) => {
      const normalized = value.trim();
      if (normalized !== (term.value ?? "")) term.value = normalized || null;
    },
    delayMs,
    { immediate: false },
  );

  function setSearch(value: string) {
    input.value = value;
    commit.start(value);
  }

  watch(term, (value) => {
    if (input.value.trim() === (value ?? "")) return;
    // A keystroke still waiting would overwrite the term just navigated to.
    commit.stop();
    input.value = value ?? "";
  });

  return { input, setSearch };
}
