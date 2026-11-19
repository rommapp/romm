import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import storeAuth from "@/stores/auth";
import RetroAchievementsSection from "./RetroAchievementsSection.vue";

const {
  fetchCurrentUser,
  updateUser,
  refreshRetroAchievements,
  snackbarError,
  socketHandlers,
} = vi.hoisted(() => ({
  fetchCurrentUser: vi.fn(),
  updateUser: vi.fn(),
  refreshRetroAchievements: vi.fn(),
  snackbarError: vi.fn(),
  socketHandlers: new Map<string, (payload: unknown) => void>(),
}));

vi.mock("@/services/api/user", () => ({
  default: { fetchCurrentUser, updateUser, refreshRetroAchievements },
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
  updateUser.mockReset();
  refreshRetroAchievements.mockReset();
  snackbarError.mockReset();
  storeAuth().user = { id: 1, ra_username: "me" } as never;
});

describe("RetroAchievementsSection", () => {
  it("reloads the user once the background sync finishes", () => {
    finishSync(true);

    expect(fetchCurrentUser).toHaveBeenCalledTimes(1);
    expect(snackbarError).not.toHaveBeenCalled();
  });

  it("reports a background sync that failed and still reloads the user", () => {
    finishSync(false);

    expect(snackbarError).toHaveBeenCalledWith("settings.ra-sync-failed", {
      icon: "mdi-close-circle",
    });
    expect(fetchCurrentUser).toHaveBeenCalledTimes(1);
  });

  it("shows the saved username before the sync finishes", async () => {
    storeAuth().user = { id: 1, ra_username: null } as never;
    fetchCurrentUser.mockResolvedValue({ data: { id: 1, ra_username: "me" } });
    updateUser.mockResolvedValue({ data: { id: 1, ra_username: "me" } });
    refreshRetroAchievements.mockResolvedValue(undefined);
    const wrapper = mount(RetroAchievementsSection);

    await wrapper.find("input").setValue("me");
    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(updateUser).toHaveBeenCalledWith({ id: 1, ra_username: "me" });
    expect(refreshRetroAchievements).toHaveBeenCalledWith({
      id: 1,
      incremental: false,
    });
    expect(storeAuth().user?.ra_username).toBe("me");
  });
});
