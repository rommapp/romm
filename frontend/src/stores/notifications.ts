import type { SnackbarStatus } from "@/types/emitter";
import { defineStore } from "pinia";

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
    clear() {
      this.notifications = [] as SnackbarStatus[];
    },
  },
});
