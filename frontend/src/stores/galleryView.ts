import { defineStore } from "pinia";

export default defineStore("galleryView", {
  state: () => ({
    currentView: JSON.parse(localStorage.getItem("currentView") ?? "0") as number,
    scrolledToTop: false,
    scroll: 0
  }),

  actions: {
    setView(view: number) {
      this.currentView = view;
      localStorage.setItem("currentView", this.currentView.toString());
    },
    next() {
      if (this.currentView == 2) {
        this.setView(0);
      } else {
        this.setView(this.currentView + 1);
      }
    },
  },
});
