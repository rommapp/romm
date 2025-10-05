import { defineStore } from "pinia";
import type { SnackbarStatus } from "@/types/emitter";

export default defineStore("notifications", {
  state: () => ({
    notifications: [] as SnackbarStatus[],
  }),

  actions: {
    add(notification: SnackbarStatus) {
      this.notifications.push(notification);
    },
    remove(id: number | undefined) {
      this.notifications = this.notifications.filter(
        (notification) => notification.id !== id,
      );
    },
    reset() {
      this.notifications = [] as SnackbarStatus[];
    },
  },
});
