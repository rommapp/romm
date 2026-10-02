import { useDebounceFn } from "@vueuse/core";
import { onScopeDispose, type Ref, ref, watch } from "vue";

/** A search box bound to a store term, debounced one way and immediate the
 *  other, so a term set by navigation shows up in the box. */
export function useDebouncedSearch(term: Ref<string | null>, delayMs = 300) {
  const input = ref(term.value ?? "");

  function apply(value: string): boolean {
    const normalized = value.trim();
    if (normalized === (term.value ?? "")) return false;
    term.value = normalized || null;
    return true;
  }

  const commit = useDebounceFn(apply, delayMs);

  function setSearch(value: string) {
    input.value = value;
    void commit(value);
  }

  /** Commits the box without waiting. Returns whether the term changed. */
  function flush(): boolean {
    commit.cancel();
    return apply(input.value);
  }

  watch(term, (value) => {
    if (input.value.trim() === (value ?? "")) return;
    // A keystroke still waiting would overwrite the term just navigated to.
    commit.cancel();
    input.value = value ?? "";
  });

  onScopeDispose(commit.cancel);

  return { input, setSearch, flush };
}
