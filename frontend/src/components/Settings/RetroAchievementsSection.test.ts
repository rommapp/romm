import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import RetroAchievementsSection from "./RetroAchievementsSection.vue";

const { fetchCurrentUser, snackbarError, socketHandlers } = vi.hoisted(() => ({
  fetchCurrentUser: vi.fn(),
  snackbarError: vi.fn(),
  socketHandlers: new Map<string, (payload: unknown) => void>(),
}));

vi.mock("@/services/api/user", () => ({
  default: { fetchCurrentUser, refreshRetroAchievements: vi.fn() },
}));

vi.mock("vue-i18n");

vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: snackbarError }),
}));
vi.mock("@/composables/useSocketEvent", () => ({
  useSocketEvent: (event: string, handler: (payload: unknown) => void) => {
    socketHandlers.set(event, handler);
    return { stop: vi.fn() };
  },
}));

function finishSync(ok: boolean) {
  mount(RetroAchievementsSection);
  socketHandlers.get("ra:synced")?.({ ok });
}

beforeEach(() => {
  socketHandlers.clear();
  fetchCurrentUser.mockReset();
  fetchCurrentUser.mockResolvedValue({ data: { id: 1, ra_username: "me" } });
  snackbarError.mockReset();
  storeAuth().user = { id: 1, ra_username: "me" } as never;
});

describe("RetroAchievementsSection", () => {
  it("reloads the user once the background sync finishes", () => {
    finishSync(true);

    expect(fetchCurrentUser).toHaveBeenCalledTimes(1);
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("reports a background sync that failed", () => {
    finishSync(false);

    expect(snackbarError).toHaveBeenCalledWith("settings.ra-sync-failed", {
      icon: "mdi-close-circle",
    });
    expect(fetchCurrentUser).not.toHaveBeenCalled();
  });
});
