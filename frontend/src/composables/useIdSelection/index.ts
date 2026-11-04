import { computed, shallowRef, type ComputedRef, type Ref } from "vue";

/**
 * Checkbox selection over a list of items identified by a numeric id.
 *
 * The set is held in a `shallowRef` and cloned on every write, so reads cost
 * no proxy and a replacement is what notifies the checkboxes.
 */
export interface IdSelection<T> {
  /** The raw ids, for passing to a list component. */
  selectedIds: Ref<ReadonlySet<number>>;
  /** The selected items still present in `items`. */
  selected: ComputedRef<T[]>;
  count: ComputedRef<number>;
  allSelected: ComputedRef<boolean>;
  someSelected: ComputedRef<boolean>;
  isSelected: (id: number) => boolean;
  toggle: (id: number) => void;
  /** Checks everything, or clears it when everything already is. */
  toggleAll: () => void;
  clear: () => void;
}

export function useIdSelection<T extends { id: number }>(
  items: () => readonly T[],
): IdSelection<T> {
  const selectedIds = shallowRef<ReadonlySet<number>>(new Set<number>());

  // Derived from the live list rather than the set's own size, so an id left
  // behind by a delete or a refresh elsewhere cannot inflate the count.
  const selected = computed(() =>
    items().filter((item) => selectedIds.value.has(item.id)),
  );
  const count = computed(() => selected.value.length);
  const allSelected = computed(
    () => items().length > 0 && count.value === items().length,
  );
  const someSelected = computed(
    () => count.value > 0 && count.value < items().length,
  );

  function isSelected(id: number): boolean {
    return selectedIds.value.has(id);
  }

  function toggle(id: number): void {
    const next = new Set(selectedIds.value);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedIds.value = next;
  }

  function toggleAll(): void {
    selectedIds.value = allSelected.value
      ? new Set<number>()
      : new Set(items().map((item) => item.id));
  }

  function clear(): void {
    selectedIds.value = new Set<number>();
  }

  return {
    selectedIds,
    selected,
    count,
    allSelected,
    someSelected,
    isSelected,
    toggle,
    toggleAll,
    clear,
  };
}
