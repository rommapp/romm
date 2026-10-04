import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { effectScope, nextTick, type EffectScope } from "vue";
import {
  setStorageUser,
  userStorage,
  userStorageKey,
  useUserLocalStorage,
} from "@/composables/useUserLocalStorage";

let scope: EffectScope;

beforeEach(() => {
  localStorage.clear();
  setStorageUser(null);
  scope = effectScope();
});

afterEach(() => {
  scope.stop();
  setStorageUser(null);
  localStorage.clear();
});

describe("userStorageKey", () => {
  it("keeps the bare key while signed out", () => {
    expect(userStorageKey("settings.theme")).toBe("settings.theme");
  });

  it("namespaces the key by user id once signed in", () => {
    setStorageUser(7);
    expect(userStorageKey("settings.theme")).toBe("user:7:settings.theme");
  });

  it("moves an unscoped value to the first user who reads it", () => {
    localStorage.setItem("settings.theme", "light");
    setStorageUser(7);
    expect(userStorage.getItem("settings.theme")).toBe("light");
    expect(localStorage.getItem("settings.theme")).toBeNull();

    setStorageUser(8);
    expect(userStorage.getItem("settings.theme")).toBeNull();
  });

  it("keeps the user's own value over an unscoped one", () => {
    localStorage.setItem("user:7:settings.theme", "dark");
    localStorage.setItem("settings.theme", "light");
    setStorageUser(7);
    expect(userStorage.getItem("settings.theme")).toBe("dark");
    expect(localStorage.getItem("settings.theme")).toBeNull();
  });
});

describe("userStorage", () => {
  it("writes and removes under the user's key", () => {
    setStorageUser(7);
    userStorage.setItem("player:1:core", "snes9x");
    expect(localStorage.getItem("user:7:player:1:core")).toBe("snes9x");
    userStorage.removeItem("player:1:core");
    expect(localStorage.getItem("user:7:player:1:core")).toBeNull();
  });
});

describe("useUserLocalStorage", () => {
  it("keeps each user's value apart on a shared browser", async () => {
    const layout = scope.run(() =>
      useUserLocalStorage("v2.gallery.layout", "grid"),
    )!;

    setStorageUser(1);
    await nextTick();
    layout.value = "list";
    await nextTick();

    setStorageUser(2);
    await nextTick();
    expect(layout.value).toBe("grid");

    setStorageUser(1);
    await nextTick();
    expect(layout.value).toBe("list");
    expect(localStorage.getItem("user:1:v2.gallery.layout")).toBe("list");
  });

  it("falls back to the default once signed out", async () => {
    const muted = scope.run(() =>
      useUserLocalStorage("soundtrack.muted", false),
    )!;

    setStorageUser(1);
    await nextTick();
    muted.value = true;
    await nextTick();

    setStorageUser(null);
    await nextTick();
    expect(muted.value).toBe(false);
  });
});
