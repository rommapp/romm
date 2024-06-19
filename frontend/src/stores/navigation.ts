import { defineStore } from "pinia";

export default defineStore("galleryView", {
  state: () => ({
    activePlatformsDrawer: false,
    activeSettingsDrawer: false,
    activeActionsDrawer: false,
  }),

  actions: {
    switchActivePlatformsDrawer(status: boolean | undefined) {
      if (status != undefined) {
        this.activePlatformsDrawer = status;
      } else {
        this.activePlatformsDrawer = !this.activePlatformsDrawer;
      }
    },
    switchActiveSettingsDrawer(status: boolean | undefined) {
      if (status != undefined) {
        this.activeSettingsDrawer = status;
      } else {
        this.activeSettingsDrawer = !this.activeSettingsDrawer;
      }
    },
    switchActiveActionsDrawer(status: boolean | undefined) {
      if (status != undefined) {
        this.activeActionsDrawer = status;
      } else {
        this.activeActionsDrawer = !this.activeActionsDrawer;
      }
    },
  },
});
