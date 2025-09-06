import { useLocalStorage } from "@vueuse/core";
import { defineStore } from "pinia";

const currentViewStorage = useLocalStorage("ui.currentView", 0);

const defaultGalleryState = {
  currentView: currentViewStorage.value,
  defaultAspectRatioCover: 2 / 3,
  defaultAspectRatioCollection: 2 / 3,
  defaultAspectRatioScreenshot: 16 / 9,
  activeFirmwareDrawer: false,
  scrolledToTop: false,
  showFabOverlay: false,
};

export default defineStore("galleryView", {
  state: () => ({ ...defaultGalleryState }),

  actions: {
    setView(view: number) {
      this.currentView = view;
      currentViewStorage.value = view;
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
    reset() {
      Object.assign(this, { ...defaultGalleryState });
    },
  },
});
