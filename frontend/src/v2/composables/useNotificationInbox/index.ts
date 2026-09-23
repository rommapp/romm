// installNotificationInbox — loads the signed-in user's notifications and keeps
// them current from their socket room. Mounted once in AppLayout.
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";
import type {
  NotificationIdsPayload,
  NotificationSchema,
} from "@/__generated__";
import socket from "@/services/socket";
import storeAuth from "@/stores/auth";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { useSocketEvent } from "@/v2/composables/useSocketEvent";
import storeNotificationInbox from "@/v2/stores/notificationInbox";
import { describeNotification } from "@/v2/utils/notifications";

export function installNotificationInbox() {
  const inbox = storeNotificationInbox();
  const { user } = storeToRefs(storeAuth());
  const snackbar = useSnackbar();
  const userId = computed(() => user.value?.id ?? null);

  // The server joins a socket to its user's room from the session it connects
  // with, so one left open across a logout would still get the last user's.
  if (socket.connected) socket.disconnect().connect();

  async function refresh() {
    try {
      await inbox.fetch();
    } catch (error) {
      console.error("Could not load notifications:", error);
    }
  }

  watch(
    userId,
    (id) => {
      if (id) void refresh();
      else inbox.reset();
    },
    { immediate: true },
  );

  useSocketEvent<NotificationSchema>("notifications:new", (notification) => {
    inbox.receive(notification);
    const view = describeNotification(notification);
    if (view.toast) {
      snackbar.show(notification.level, view.title, { icon: view.icon });
    }
  });

  // Another of the user's tabs read or dismissed some.
  useSocketEvent<NotificationIdsPayload>("notifications:read", ({ ids }) => {
    inbox.applyRead(ids ?? null);
  });

  useSocketEvent<NotificationIdsPayload>(
    "notifications:dismissed",
    ({ ids }) => {
      inbox.applyDismissed(ids ?? null);
    },
  );

  // A push sent while the socket was down only reached the stored list.
  let connectedBefore = false;
  useSocketEvent("connect", () => {
    if (connectedBefore && userId.value) void refresh();
    connectedBefore = true;
  });
}
