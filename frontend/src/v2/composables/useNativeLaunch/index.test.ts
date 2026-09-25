import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { LaunchState } from "@/types/rommNative";
import { installNativeLaunchFeedback } from "./index";

// The shell's own launch-state stream, so a test can play back what it sends.
let emit: ((state: LaunchState) => void) | null = null;
const unsubscribe = vi.fn();

vi.mock("@/services/native", () => ({
  onNativeLaunchState: (listener: (state: LaunchState) => void) => {
    emit = listener;
    return unsubscribe;
  },
}));

const install = vi.fn();
const nameFor = vi.fn(() => "Chrono Trigger");
const consumeCancelled = vi.fn(() => false);
vi.mock("@/stores/native", () => ({
  useNativeStore: () => ({ install, nameFor, consumeCancelled }),
}));

const success = vi.fn();
const error = vi.fn();
const warning = vi.fn();
const info = vi.fn();
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error, warning, info }),
}));

const t = vi.fn((key: string) => key);
vi.mock("vue-i18n", () => ({ useI18n: () => ({ t }) }));

// The composable only runs inside a component scope, like AppLayout's. The
// wrapper is kept so each test's subscription dies with it.
let wrapper: ReturnType<typeof mount> | null = null;
function feedback() {
  wrapper = mount(
    defineComponent({
      setup() {
        installNativeLaunchFeedback();
        return () => null;
      },
    }),
  );
}

describe("installNativeLaunchFeedback", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    emit = null;
    install.mockClear();
    nameFor.mockClear();
    nameFor.mockImplementation(() => "Chrono Trigger");
    consumeCancelled.mockClear();
    success.mockClear();
    error.mockClear();
    warning.mockClear();
    info.mockClear();
    t.mockClear();
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    wrapper?.unmount();
    wrapper = null;
    vi.restoreAllMocks();
  });

  it("subscribes on install", () => {
    feedback();

    expect(install).toHaveBeenCalledTimes(1);
    expect(emit).not.toBeNull();
  });

  it("raises the save the shell pulled, naming the game", () => {
    feedback();

    emit?.({ romId: 7, status: "sync", sync: { action: "downloaded" } });

    expect(success).toHaveBeenCalledWith("play.native-save-downloaded", {
      icon: "mdi-download-outline",
    });
    expect(t).toHaveBeenCalledWith("play.native-save-downloaded", {
      name: "Chrono Trigger",
    });
  });

  it("raises the save the shell sent", () => {
    feedback();

    emit?.({ romId: 7, status: "sync", sync: { action: "uploaded" } });

    expect(success).toHaveBeenCalledWith("play.native-save-uploaded", {
      icon: "mdi-upload-outline",
    });
  });

  // An archival save is the only user-visible consequence of a conflict, so it
  // is a warning rather than another success among the successes.
  it("warns when the shell kept a save aside", () => {
    feedback();

    emit?.({ romId: 7, status: "sync", sync: { action: "archived" } });

    expect(warning).toHaveBeenCalledWith("play.native-save-archived", {
      icon: "mdi-archive-outline",
    });
    expect(success).not.toHaveBeenCalled();
  });

  it("reports a save the shell could not move, and its reason", () => {
    feedback();

    emit?.({
      romId: 7,
      status: "sync",
      sync: { action: "failed", detail: "409 from /api/saves" },
    });

    expect(error).toHaveBeenCalledWith("play.native-save-failed", {
      icon: "mdi-alert-circle-outline",
    });
    expect(console.error).toHaveBeenCalledWith(
      "[native] Save sync failed:",
      "409 from /api/saves",
    );
  });

  // A save moving is not a launch ending: the emulator has already exited, and
  // nothing about the launch is worth repeating.
  it("says nothing about the launch the save moved around", () => {
    feedback();

    emit?.({ romId: 7, status: "sync", sync: { action: "downloaded" } });

    expect(success).not.toHaveBeenCalledWith(
      "play.native-running",
      expect.anything(),
    );
    expect(consumeCancelled).not.toHaveBeenCalled();
  });

  it("stays quiet on a sync status that carries no outcome", () => {
    feedback();

    emit?.({ romId: 7, status: "sync" });

    expect(success).not.toHaveBeenCalled();
    expect(warning).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });
});
