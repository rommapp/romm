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
    switchActivePlatformSettingsDrawer() {
      this.resetDrawersExcept("activePlatformSettingsDrawer");
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
      this.activePlatformSettingsDrawer =
        drawer === "activePlatformSettingsDrawer"
          ? this.activePlatformSettingsDrawer
          : false;
    },
  },
});
