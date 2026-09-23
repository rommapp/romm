import { beforeAll, describe, expect, it } from "vitest";
import type { NotificationKind, NotificationSchema } from "@/__generated__";
import { loadLocale } from "@/locales";
import { ROUTES } from "@/plugins/routeNames";
import { describeNotification } from "@/v2/utils/notifications";
import { makeNotification } from "@/v2/utils/notifications.fixtures";

function notification(
  kind: NotificationKind | string,
  data: NotificationSchema["data"] = {},
): NotificationSchema {
  return makeNotification({ kind, data });
}

beforeAll(async () => {
  await loadLocale("en_US");
});

describe("describeNotification", () => {
  it("counts the games a scan added", () => {
    const view = describeNotification(
      notification("scan_completed", { new_roms: 3 }),
    );

    expect(view.title).toBe("Scan completed");
    expect(view.body).toBe("3 new games");
    expect(view.to).toEqual({ name: ROUTES.SCAN });
  });

  it("says so when a scan added nothing", () => {
    const view = describeNotification(
      notification("scan_completed", { new_roms: 0 }),
    );

    expect(view.body).toBe("No new games");
  });

  it("leaves scan toasts to the scan's own live events", () => {
    expect(describeNotification(notification("scan_completed")).toast).toBe(
      false,
    );
    expect(describeNotification(notification("scan_failed")).toast).toBe(false);
  });

  it("shows why a task failed", () => {
    const view = describeNotification(
      notification("task_failed", {
        task: "cleanup_missing_roms",
        title: "Cleanup Missing ROMs",
        error: "disk full",
      }),
    );

    expect(view.title).toBe("Cleanup Missing ROMs failed");
    expect(view.body).toBe("disk full");
    expect(view.toast).toBe(true);
  });

  it("links an ended stream to its game and carries the admin's reason", () => {
    const view = describeNotification(
      notification("streaming_session_ended", {
        rom_id: 42,
        rom_name: "Metroid",
        reason: "maintenance",
      }),
    );

    expect(view.title).toBe("Your stream of Metroid was ended");
    expect(view.body).toBe("maintenance");
    expect(view.to).toEqual({ name: ROUTES.ROM, params: { rom: 42 } });
  });

  it("names the new role in the reader's language", () => {
    const view = describeNotification(
      notification("role_changed", { role: "admin" }),
    );

    expect(view.title).toBe("Your role is now Admin");
  });

  it("shows a custom notification with its own content", () => {
    const view = describeNotification({
      ...notification("argosy.sync_done"),
      title: "Sync finished",
      body: "12 saves uploaded",
      link: "/rom/12",
      icon: "mdi-sync",
    });

    expect(view).toEqual({
      icon: "mdi-sync",
      title: "Sync finished",
      body: "12 saves uploaded",
      to: "/rom/12",
      toast: true,
    });
  });

  it("never links outside RomM", () => {
    const view = describeNotification({
      ...notification("custom", {}),
      title: "Hi",
      link: "//evil.example/login",
    });

    expect(view.to).toBeNull();
  });

  it("still renders a kind this client doesn't know", () => {
    const view = describeNotification(notification("from_the_future"));

    expect(view.title).toBe("New notification");
    expect(view.icon).toBe("mdi-information-outline");
    expect(view.to).toBeNull();
  });
});
