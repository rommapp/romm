import { defineStore } from "pinia";

export default defineStore("navigation", {
  state: () => ({
    activePlatformsDrawer: false,
    activeSettingsDrawer: false,
  }),

  actions: {
    switchActivePlatformsDrawer() {
      this.activeSettingsDrawer = false;
      this.activePlatformsDrawer = !this.activePlatformsDrawer;
    },
    switchActiveSettingsDrawer() {
      this.activePlatformsDrawer = false;
      this.activeSettingsDrawer = !this.activeSettingsDrawer;
    },
    goHome() {
      this.resetDrawers();
      this.$router.push({ name: "dashboard" });
    },
    goScan() {
      this.resetDrawers();
      this.$router.push({ name: "scan" });
    },
    resetDrawers() {
      this.activePlatformsDrawer = false;
      this.activeSettingsDrawer = false;
    },
  },
});
