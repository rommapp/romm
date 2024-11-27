import { defineStore } from "pinia";

export default defineStore("galleryView", {
  state: () => ({
    currentView: JSON.parse(
      localStorage.getItem("currentView") ?? "0",
    ) as number,
    aspectRatioCover: 2 / 3,
    aspectRatioCollection: 2 / 3,
    aspectRatioScreenshot: 16 / 9,
    activeFirmwareDrawer: false,
    scrolledToTop: false,
    scroll: 0,
  }),

  actions: {
    setView(view: number) {
      this.currentView = view;
      localStorage.setItem("currentView", this.currentView.toString());
    },
    switchActiveFirmwareDrawer() {
      this.activeFirmwareDrawer = !this.activeFirmwareDrawer;
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
