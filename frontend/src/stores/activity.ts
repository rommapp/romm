import { defineStore } from "pinia";
import activityApi, {
  type ActivityClearEvent,
  type ActivityEntry,
} from "@/services/api/activity";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";

export type { ActivityEntry, ActivityClearEvent };

export default defineStore("activity", {
  state: () => ({
    activities: [] as ActivityEntry[],
    initialized: false,
    socketBound: false,
    // Bumped by each socket event, so a fetch that raced one can tell.
    version: 0,
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
        for (let attempt = 1; ; attempt++) {
          const version = this.version;
          const { data } = await activityApi.getAllActivity();
          // An event that landed mid-request may be missing, so ask again.
          if (version !== this.version && attempt < 3) continue;
          this.activities = data;
          this.initialized = true;
          return;
        }
      } catch (error) {
        console.error("Error fetching activity:", error);
      }
    },

    handleUpdate(entry: ActivityEntry) {
      this.version++;
      const idx = this.activities.findIndex(
        (a) => a.user_id === entry.user_id && a.device_id === entry.device_id,
      );
      if (idx >= 0) {
        // Replace the entry so reactive getters pick up the change.
        this.activities.splice(idx, 1, entry);
      } else {
        this.activities.push(entry);
      }
    },

    handleClear(data: ActivityClearEvent) {
      this.version++;
      // A clear for the device's previous game must not drop its current one.
      this.activities = this.activities.filter(
        (a) =>
          !(
            a.user_id === data.user_id &&
            a.device_id === data.device_id &&
            a.rom_id === data.rom_id
          ),
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
      // A newly hidden ROM's session gets no clear here, so re-list what's visible.
      socket.on("permissions:changed", (data: { user_id: number }) => {
        if (data.user_id === storeAuth().user?.id) this.fetchAll();
      });

      this.socketBound = true;
    },

    reset() {
      this.activities = [];
      this.initialized = false;
    },
  },
});
