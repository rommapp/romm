import { onScopeDispose, type Ref, ref, watch } from "vue";

/** A search box bound to a store term: typing writes the trimmed term after
 *  `delayMs`, and a term set elsewhere (back/forward, a pasted link) shows up
 *  in the box straight away. */
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
