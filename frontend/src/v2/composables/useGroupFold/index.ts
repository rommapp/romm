import { ref, watch, type Ref } from "vue";

interface GroupFoldOptions<G> {
  groups: Ref<readonly G[]>;
  keyOf: (group: G) => string;
  /** Whether the group holds the current selection; it opens when it does. */
  holdsSelection: (group: G) => boolean;
  defaultOpen: (group: G) => boolean;
  selectedId: () => number | null;
}

/**
 * Open state for foldable groups: a group opens on its own when it takes the
 * selection, while an explicit toggle wins until the selection moves again.
 */
export function useGroupFold<G>(options: GroupFoldOptions<G>) {
  const overrides = ref(new Map<string, boolean>());

  function isOpen(group: G): boolean {
    return (
      overrides.value.get(options.keyOf(group)) ??
      (options.holdsSelection(group) || options.defaultOpen(group))
    );
  }

  function toggle(group: G) {
    overrides.value.set(options.keyOf(group), !isOpen(group));
  }

  /** Opens every group, so nothing the caller is about to act on stays hidden. */
  function openAll() {
    for (const group of options.groups.value) {
      overrides.value.set(options.keyOf(group), true);
    }
  }

  watch(options.selectedId, () => {
    for (const group of options.groups.value) {
      if (options.holdsSelection(group)) {
        overrides.value.delete(options.keyOf(group));
      }
    }
  });

  return { isOpen, toggle, openAll };
}
