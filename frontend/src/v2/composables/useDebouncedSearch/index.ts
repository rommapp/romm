import { onScopeDispose, type Ref, ref, watch } from "vue";

/** A search box bound to a store term, debounced one way and immediate the
 *  other, so a term set by navigation shows up in the box. */
export function useDebouncedSearch(term: Ref<string | null>, delayMs = 300) {
  const input = ref(term.value ?? "");
  let pending: ReturnType<typeof setTimeout> | null = null;

  function cancel() {
    if (pending) clearTimeout(pending);
    pending = null;
  }

  function setSearch(value: string) {
    input.value = value;
    cancel();
    pending = setTimeout(() => {
      pending = null;
      const normalized = value.trim();
      if (normalized !== (term.value ?? "")) term.value = normalized || null;
    }, delayMs);
  }

  watch(term, (value) => {
    if (input.value.trim() === (value ?? "")) return;
    // A keystroke still waiting would overwrite the term just navigated to.
    cancel();
    input.value = value ?? "";
  });

  onScopeDispose(cancel);

  return { input, setSearch };
}
