import { defineStore } from "pinia";

export default defineStore("navigation", {
  state: () => ({
    activePlatformsDrawer: false,
    activeCollectionsDrawer: false,
    activeSettingsDrawer: false,
    activePlatformInfoDrawer: false,
    activePlatformSettingsDrawer: false,
  }),

  actions: {
    switchActivePlatformsDrawer() {
      this.resetDrawers();
      this.activePlatformsDrawer = !this.activePlatformsDrawer;
    },
    switchActiveCollectionsDrawer() {
      this.resetDrawers();
      this.activeCollectionsDrawer = !this.activeCollectionsDrawer;
    },
    switchActiveSettingsDrawer() {
      this.resetDrawers();
      this.activeSettingsDrawer = !this.activeSettingsDrawer;
    },
    switchActivePlatformInfoDrawer() {
      this.resetDrawers();
      this.activePlatformInfoDrawer = !this.activePlatformInfoDrawer;
    },
    switchActivePlatformSettingsDrawer() {
      this.resetDrawers();
      this.activePlatformSettingsDrawer = !this.activePlatformSettingsDrawer;
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
      this.activeCollectionsDrawer = false;
      this.activeSettingsDrawer = false;
      this.activePlatformInfoDrawer = false;
      this.activePlatformSettingsDrawer = false;
    },
  },
});
