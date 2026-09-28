// installNotificationInbox: loads the signed-in user's notifications and keeps
// them current from their socket room. Mounted once in AppLayout.
import { storeToRefs } from "pinia";
import { computed, watch } from "vue";
import type {
  NotificationIdsPayload,
  NotificationSchema,
} from "@/__generated__";
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

  async function refresh() {
    try {
      await inbox.fetch();
    } catch (error) {
      console.error("Could not load notifications:", error);
    }
  }

  // Cleared first, so a failed fetch can't leave the last user's inbox behind.
  watch(
    userId,
    (id) => {
      inbox.reset();
      if (id) void refresh();
    },
    { immediate: true },
  );

  // This tab already toasted what it sent itself.
  useSocketEvent<NotificationSchema>("notifications:new", (notification) => {
    if (!inbox.receive(notification) || inbox.sentFromThisTab(notification)) {
      return;
    }
    const view = describeNotification(notification);
    if (view.toast) {
      snackbar.show(notification.level, view.title, { icon: view.icon });
    }
  });

  // Another of the user's tabs read or dismissed some.
  useSocketEvent<NotificationIdsPayload>("notifications:read", ({ ids }) => {
    inbox.applyRead(ids);
  });

  useSocketEvent<NotificationIdsPayload>(
    "notifications:dismissed",
    ({ ids }) => {
      inbox.applyDismissed(ids);
    },
  );

  // A push sent while the socket was down only reached the stored list.
  let connectedBefore = false;
  useSocketEvent("connect", () => {
    if (connectedBefore && userId.value) void refresh();
    connectedBefore = true;
  });
}
