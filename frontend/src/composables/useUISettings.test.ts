import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import { setStorageUser } from "@/composables/useUserLocalStorage";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";

const { updateUser } = vi.hoisted(() => ({ updateUser: vi.fn() }));
vi.mock("@/services/api/user", () => ({ default: { updateUser } }));

const userWith = (id: number, ui_settings: Record<string, unknown>) =>
  userFixture({ id, ui_settings });

beforeEach(() => {
  vi.useFakeTimers();
  localStorage.clear();
  setActivePinia(createPinia());
  updateUser.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  setStorageUser(null);
  localStorage.clear();
});

describe("useUISettings", () => {
  it("applies the next user's settings on sign-in without saving them back", async () => {
    const authStore = storeAuth();
    watch(() => authStore.user?.id ?? null, setStorageUser, {
      immediate: true,
      flush: "sync",
    });

    authStore.setCurrentUser(userWith(1, { theme: "dark" }));
    const { theme, similarGamesSource } = useUISettings();
    expect(similarGamesSource.value).toBe("romm");
    await nextTick();
    vi.runAllTimers();
    expect(theme.value).toBe("dark");

    authStore.setCurrentUser(null);
    await nextTick();
    localStorage.setItem("user:2:settings.theme", "dark");
    authStore.setCurrentUser(
      userWith(2, { theme: "light", similarGamesSource: "igdb" }),
    );
    await nextTick();
    vi.runAllTimers();
    await nextTick();

    expect(theme.value).toBe("light");
    expect(similarGamesSource.value).toBe("igdb");
    expect(localStorage.getItem("user:2:settings.similarGamesSource")).toBe(
      "igdb",
    );
    expect(localStorage.getItem("user:1:settings.theme")).toBe("dark");
    expect(updateUser).not.toHaveBeenCalled();

    updateUser.mockResolvedValue({
      data: userWith(2, { similarGamesSource: "romm" }),
    });
    similarGamesSource.value = "romm";
    await nextTick();
    expect(updateUser).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 2,
        ui_settings: expect.stringContaining('"similarGamesSource":"romm"'),
      }),
    );
  });
});
