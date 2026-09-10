import { defineStore } from "pinia";

export default defineStore("playing", {
  state: () => ({
    playing: false,
    fullScreen: false,
    // True while a player's running stage covers the viewport; the v2
    // AppLayout unmounts the nav chrome and zeroes the nav-height tokens.
    stageActive: false,
  }),

  actions: {
    setPlaying(playing: boolean) {
      this.playing = playing;
    },
    setFullScreen(fullScreen: boolean) {
      this.fullScreen = fullScreen;
    },
    setStageActive(stageActive: boolean) {
      this.stageActive = stageActive;
    },
  },
});
