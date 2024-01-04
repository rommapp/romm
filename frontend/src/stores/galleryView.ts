import { defineStore } from "pinia";

export default defineStore("galleryView", {
  state: () => ({
    current: JSON.parse(localStorage.getItem("currentView") ?? "0") as number,
  }),

  actions: {
    set(view: number) {
      this.current = view;
      localStorage.setItem("currentView", this.current.toString());
    },
    next() {
      if (this.current == 2) {
        this.set(0);
      } else {
        this.set(this.current + 1);
      }
    },
  },
});
