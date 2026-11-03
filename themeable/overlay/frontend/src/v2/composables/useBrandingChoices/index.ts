// useBrandingChoices (romm-themeable): Branding's unsaved theme choice and Random groups. They take
// the server's saved values from the first status and after a save, and survive every other refresh.
import { ref, watch, type Ref } from "vue";
import type { BrandingStatus, RandomGroups } from "@/services/api/themeable";

export function useBrandingChoices(status: Ref<BrandingStatus | null>) {
  const selected = ref("");
  const groups = ref<RandomGroups>({
    stock: false,
    built_in: true,
    accessibility: true,
  });
  let adopt = true;

  watch(status, (value) => {
    if (!value) return;
    const stock = value.client?.stock_id ?? "";
    const ids = [
      value.client?.random_id,
      stock,
      ...value.packs.map((p) => p.id),
    ];
    if (adopt) {
      adopt = false;
      if (value.random) {
        const { stock: drawStock, built_in, accessibility } = value.random;
        groups.value = { stock: drawStock, built_in, accessibility };
      }
      selected.value = ids.includes(value.selected) ? value.selected : stock;
    } else if (!ids.includes(selected.value)) {
      // The chosen pack was deleted.
      selected.value = stock;
    }
  });

  /** Lets the next status replace the edits, as after a successful save. */
  function adoptNext(): void {
    adopt = true;
  }

  return { selected, groups, adoptNext };
}
