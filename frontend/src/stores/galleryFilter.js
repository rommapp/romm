import { defineStore } from "pinia";
import { normalizeString } from "@/utils/utils";

export default defineStore("galleryFilter", {
  state: () => ({ filter: "" }),

  actions: {
    set(filter) {
      this.filter = normalizeString(filter);
    },
  },
});
