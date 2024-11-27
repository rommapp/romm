import { defineStore } from "pinia";

export default defineStore("navigation", {
  state: () => ({
    activePlatformsDrawer: false,
    activeCollectionsDrawer: false,
    activeSettingsDrawer: false,
    activePlatformInfoDrawer: false,
  }),

  actions: {
    switchActivePlatformsDrawer() {
      this.activeCollectionsDrawer = false;
      this.activeSettingsDrawer = false;
      this.activePlatformsDrawer = !this.activePlatformsDrawer;
      this.activePlatformInfoDrawer = false;
    },
    switchActiveCollectionsDrawer() {
      this.activePlatformsDrawer = false;
      this.activeSettingsDrawer = false;
      this.activeCollectionsDrawer = !this.activeCollectionsDrawer;
      this.activePlatformInfoDrawer = false;
    },
    switchActiveSettingsDrawer() {
      this.activePlatformsDrawer = false;
      this.activeCollectionsDrawer = false;
      this.activeSettingsDrawer = !this.activeSettingsDrawer;
      this.activePlatformInfoDrawer = false;
    },
    switchActivePlatformInfoDrawer() {
      this.activePlatformsDrawer = false;
      this.activeCollectionsDrawer = false;
      this.activeSettingsDrawer = false;
      this.activePlatformInfoDrawer = !this.activePlatformInfoDrawer;
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
    },
  },
});
