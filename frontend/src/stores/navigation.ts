import { useLocalStorage } from "@vueuse/core";
import { defineStore } from "pinia";
import { ROUTES } from "@/plugins/router";

const mainBarCollapsed = useLocalStorage("ui.mainBarCollapsed", false);

const defaultNavigationState = {
  activePlatformsDrawer: false,
  activeCollectionsDrawer: false,
  activeSettingsDrawer: false,
  activePlatformInfoDrawer: false,
  activeCollectionInfoDrawer: false,
  mainBarCollapsed: mainBarCollapsed.value,
};

export default defineStore("navigation", {
  state: () => ({ ...defaultNavigationState }),

  actions: {
    switchActivePlatformsDrawer() {
      this.resetDrawersExcept("activePlatformsDrawer");
      this.activePlatformsDrawer = !this.activePlatformsDrawer;
    },
    switchActiveCollectionsDrawer() {
      this.resetDrawersExcept("activeCollectionsDrawer");
      this.activeCollectionsDrawer = !this.activeCollectionsDrawer;
    },
    switchActiveSettingsDrawer() {
      this.resetDrawersExcept("activeSettingsDrawer");
      this.activeSettingsDrawer = !this.activeSettingsDrawer;
    },
    switchActivePlatformInfoDrawer() {
      this.resetDrawersExcept("activePlatformInfoDrawer");
      this.activePlatformInfoDrawer = !this.activePlatformInfoDrawer;
    },
    switchActiveCollectionInfoDrawer() {
      this.resetDrawersExcept("activeCollectionInfoDrawer");
      this.activeCollectionInfoDrawer = !this.activeCollectionInfoDrawer;
    },
    goHome() {
      this.reset();
      this.$router.push({ name: ROUTES.HOME });
    },
    goScan() {
      this.reset();
      this.$router.push({ name: ROUTES.SCAN });
    },
    goSearch() {
      this.reset();
      this.$router.push({ name: ROUTES.SEARCH });
    },
    reset() {
      Object.assign(this, { ...defaultNavigationState });
    },
    resetDrawersExcept(drawer: string) {
      this.activePlatformsDrawer =
        drawer === "activePlatformsDrawer" ? this.activePlatformsDrawer : false;
      this.activeCollectionsDrawer =
        drawer === "activeCollectionsDrawer"
          ? this.activeCollectionsDrawer
          : false;
      this.activeSettingsDrawer =
        drawer === "activeSettingsDrawer" ? this.activeSettingsDrawer : false;
      this.activePlatformInfoDrawer =
        drawer === "activePlatformInfoDrawer"
          ? this.activePlatformInfoDrawer
          : false;
      this.activeCollectionInfoDrawer =
        drawer === "activeCollectionInfoDrawer"
          ? this.activeCollectionInfoDrawer
          : false;
    },
  },
});
