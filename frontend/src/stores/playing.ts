import { defineStore } from "pinia";

export default defineStore("playing", {
  state: () => ({
    playing: false,
    // Written by v1 players; nothing reads it.
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
