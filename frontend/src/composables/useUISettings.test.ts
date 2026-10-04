import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import { setStorageUser } from "@/composables/useUserLocalStorage";
import storeAuth from "@/stores/auth";
import type { User } from "@/stores/users";

const { updateUser } = vi.hoisted(() => ({ updateUser: vi.fn() }));
vi.mock("@/services/api/user", () => ({ default: { updateUser } }));

const userWith = (id: number, ui_settings: Record<string, unknown>) =>
  ({ id, ui_settings }) as unknown as User;

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
    const { theme } = useUISettings();
    await nextTick();
    vi.runAllTimers();
    expect(theme.value).toBe("dark");

    authStore.setCurrentUser(null);
    await nextTick();
    localStorage.setItem("user:2:settings.theme", "dark");
    authStore.setCurrentUser(userWith(2, { theme: "light" }));
    await nextTick();
    vi.runAllTimers();
    await nextTick();

    expect(theme.value).toBe("light");
    expect(localStorage.getItem("user:1:settings.theme")).toBe("dark");
    expect(updateUser).not.toHaveBeenCalled();
  });
});
