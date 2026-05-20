import { defineStore } from "pinia";
import activityApi, {
  type ActivityClearEvent,
  type ActivityEntry,
} from "@/services/api/activity";
import socket from "@/services/socket";

export type { ActivityEntry, ActivityClearEvent };

export default defineStore("activity", {
  state: () => ({
    activities: [] as ActivityEntry[],
    initialized: false,
    socketBound: false,
  }),

  getters: {
    getByRomId:
      (state) =>
      (romId: number): ActivityEntry[] =>
        state.activities.filter((a) => a.rom_id === romId),

    getByUserId:
      (state) =>
      (userId: number): ActivityEntry[] =>
        state.activities.filter((a) => a.user_id === userId),

    activeCount: (state): number => state.activities.length,

    activeUserCount: (state): number =>
      new Set(state.activities.map((a) => a.user_id)).size,
  },

  actions: {
    async fetchAll() {
      try {
        const { data } = await activityApi.getAllActivity();
        this.activities = data;
        this.initialized = true;
      } catch (error) {
        console.error("Error fetching activity:", error);
      }
    },

    handleUpdate(entry: ActivityEntry) {
      const idx = this.activities.findIndex(
        (a) =>
          a.user_id === entry.user_id && a.device_id === entry.device_id,
      );
      if (idx >= 0) {
        // Replace the entry so reactive getters pick up the change.
        this.activities.splice(idx, 1, entry);
      } else {
        this.activities.push(entry);
      }
    },

    handleClear(data: ActivityClearEvent) {
      this.activities = this.activities.filter(
        (a) =>
          !(a.user_id === data.user_id && a.device_id === data.device_id),
      );
    },

    initSocket() {
      if (this.socketBound) return;
      if (!socket.connected) socket.connect();

      socket.on("activity:update", (entry: ActivityEntry) => {
        this.handleUpdate(entry);
      });
      socket.on("activity:clear", (data: ActivityClearEvent) => {
        this.handleClear(data);
      });

      this.socketBound = true;
    },

    reset() {
      this.activities = [];
      this.initialized = false;
    },
  },
});
