import { defineStore } from "pinia";

export default defineStore("navigation", {
  state: () => ({
    activePlatformsDrawer: false,
    activeSettingsDrawer: false,
  }),

  actions: {
    switchActivePlatformsDrawer() {
      this.activePlatformsDrawer = !this.activePlatformsDrawer;
    },
    switchActiveSettingsDrawer() {
      this.activeSettingsDrawer = !this.activeSettingsDrawer;
    },
    resetDrawers() {
      this.activePlatformsDrawer = false;
      this.activeSettingsDrawer = false;
    },
  },
});
