import { defineStore } from "pinia";

export default defineStore("galleryView", {
  state: () => ({
    current: JSON.parse(localStorage.getItem("currentView") ?? "0") as number,
    scrolledToTop: false
  }),

  actions: {
    setView(view: number) {
      this.current = view;
      localStorage.setItem("currentView", this.current.toString());
    },
    next() {
      if (this.current == 2) {
        this.setView(0);
      } else {
        this.setView(this.current + 1);
      }
    },
  },
});
