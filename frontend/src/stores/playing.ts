import { defineStore } from "pinia";

export default defineStore("playing", {
  state: () => ({
    playing: false,
    fullScreen: false,
    // True while a running player stage owns the viewport (see useStageActive).
    stageActive: false,
  }),

  actions: {
    setPlaying(playing: boolean) {
      this.playing = playing;
    },
    setStageActive(stageActive: boolean) {
      this.stageActive = stageActive;
    },
  },
});
