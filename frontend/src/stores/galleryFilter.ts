import { defineStore } from "pinia";
import { normalizeString } from "@/utils";

export default defineStore("galleryFilter", {
  state: () => ({ filter: "" }),

  actions: {
    set(filter: string) {
      this.filter = normalizeString(filter);
    },
  },
});
