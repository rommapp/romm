// Format downloads waiting on the server to convert, keyed by download path
// so a second click on the same format dedupes.
import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface FormatConversion {
  href: string;
  romId: number;
  romName: string;
  format: string;
}

export default defineStore("v2FormatConversions", () => {
  const conversions = ref<FormatConversion[]>([]);

  const active = computed(() => conversions.value.length > 0);

  function has(href: string) {
    return conversions.value.some((c) => c.href === href);
  }

  function add(conversion: FormatConversion) {
    if (has(conversion.href)) return;
    conversions.value = [...conversions.value, conversion];
  }

  function remove(href: string) {
    conversions.value = conversions.value.filter((c) => c.href !== href);
  }

  return { conversions, active, has, add, remove };
});
