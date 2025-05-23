import { defineStore } from "pinia";

export default defineStore("playing", {
  state: () => ({
    playing: false,
    fullScreen: false,
  }),

  actions: {
    setPlaying(playing: boolean) {
      this.playing = playing;
    },
    setFullScreen(fullScreen: boolean) {
      this.fullScreen = fullScreen;
    },
  },
});
