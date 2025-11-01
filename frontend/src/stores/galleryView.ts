import { useLocalStorage } from "@vueuse/core";
import { defineStore } from "pinia";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import storePlatforms from "@/stores/platforms";

const currentViewStorage = useLocalStorage("ui.currentView", 0);
const boxartStyleStorage = useLocalStorage<BoxartStyleOption>(
  "settings.boxartStyle",
  "cover_path",
);

const defaultGalleryState = {
  currentView: currentViewStorage.value,
  currentBoxartStyle: boxartStyleStorage.value,
  defaultAspectRatio: 2 / 3,
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
    getAspectRatio({
      platformId,
      boxartStyle,
    }: {
      platformId?: number;
      boxartStyle?: BoxartStyleOption;
    }) {
      // 3D, physical and mixed cases have custom aspect ratios
      const _boxartStyle = boxartStyle || this.currentBoxartStyle;
      if (_boxartStyle === "box3d_path") return 3 / 4;
      if (_boxartStyle === "physical_path") return 1 / 1;
      if (_boxartStyle === "miximage_path") return 1 / 1;

      const platformsStore = storePlatforms();
      const platform = platformId ? platformsStore.get(platformId) : null;
      if (platform?.aspect_ratio) {
        return (
          parseInt(platform.aspect_ratio.split("/")[0]) /
          parseInt(platform.aspect_ratio.split("/")[1])
        );
      }

      return this.defaultAspectRatio;
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
