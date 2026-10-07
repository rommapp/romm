// Format downloads waiting on the server to convert, keyed by download path.
import { defineStore } from "pinia";
import { ref } from "vue";

export interface FormatConversion {
  href: string;
  romId: number;
  romName: string;
  format: string;
}

export default defineStore("v2FormatConversions", () => {
  const conversions = ref<FormatConversion[]>([]);

  function add(conversion: FormatConversion) {
    conversions.value = [...conversions.value, conversion];
  }

  function remove(href: string) {
    if (!conversions.value.some((c) => c.href === href)) return;
    conversions.value = conversions.value.filter((c) => c.href !== href);
  }

  return { conversions, add, remove };
});
