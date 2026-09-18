import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  PlatformSupportQuery,
  RommNativeBridge,
} from "@/types/rommNative";
import {
  canSyncSaves,
  cancelNative,
  fetchPlatformSupport,
  hasCapability,
  isNativeShell,
  nativeErrorMessage,
  openNativeSettings,
} from "./native";

// The shell's own cap on a bulk query, vendored in the service under test.
const MAX_PLATFORM_QUERIES = 512;

function queries(count: number): PlatformSupportQuery[] {
  return Array.from({ length: count }, (_, i) => ({
    platformSlug: `p${i}`,
    cores: [],
  }));
}

function supported(qs: PlatformSupportQuery[]) {
  return Object.fromEntries(
    qs.map((q) => [q.platformSlug, { supported: true, emulator: "RetroArch" }]),
  );
}

function installBridge(bridge: Partial<RommNativeBridge>): void {
  window.rommNative = bridge as RommNativeBridge;
}

beforeEach(() => {
  delete window.rommNative;
  vi.restoreAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("isNativeShell", () => {
  it("is false in an ordinary browser tab", () => {
    expect(isNativeShell()).toBe(false);
  });

  it("is false on a bridge that cannot launch", () => {
    installBridge({ shellVersion: "0.1.0" });
    expect(isNativeShell()).toBe(false);
  });
});

describe("hasCapability", () => {
  it("is false with no bridge, and on one that lists nothing", () => {
    expect(hasCapability("save-sync")).toBe(false);

    installBridge({ shellVersion: "0.1.0" });
    expect(hasCapability("save-sync")).toBe(false);
  });

  it("reads the advertised list", () => {
    installBridge({ shellVersion: "0.2.0", capabilities: ["save-sync"] });

    expect(hasCapability("save-sync")).toBe(true);
  });
});

describe("canSyncSaves", () => {
  // A shell predating save sync still launches games; its saves just stay on
  // this disk. Nothing is broken by asking it to move them.
  it("is false on a shell too old to list capabilities", () => {
    installBridge({ launch: vi.fn(), shellVersion: "0.1.0" });

    expect(canSyncSaves()).toBe(false);
  });

  it("is true once the shell advertises it", () => {
    installBridge({
      launch: vi.fn(),
      shellVersion: "0.2.0",
      capabilities: ["save-sync"],
    });

    expect(canSyncSaves()).toBe(true);
  });
});

describe("fetchPlatformSupport — the bulk query", () => {
  it("asks in batches no larger than the shell accepts", async () => {
    const getPlatformSupportAll = vi
      .fn()
      .mockImplementation((qs: PlatformSupportQuery[]) =>
        Promise.resolve(supported(qs)),
      );
    installBridge({ getPlatformSupportAll });

    const answers = await fetchPlatformSupport(queries(1100));

    expect(getPlatformSupportAll.mock.calls.map(([qs]) => qs.length)).toEqual([
      MAX_PLATFORM_QUERIES,
      MAX_PLATFORM_QUERIES,
      1100 - MAX_PLATFORM_QUERIES * 2,
    ]);
    expect(Object.keys(answers)).toHaveLength(1100);
  });

  // The shell rejects an oversized batch whole, so one refusal must not read as
  // "no platform can be launched".
  it("keeps the batches that answered when one is refused", async () => {
    const getPlatformSupportAll = vi
      .fn()
      .mockRejectedValueOnce(new Error("too many"))
      .mockImplementation((qs: PlatformSupportQuery[]) =>
        Promise.resolve(supported(qs)),
      );
    installBridge({ getPlatformSupportAll });

    const answers = await fetchPlatformSupport(queries(600));

    expect(Object.keys(answers)).toHaveLength(600 - MAX_PLATFORM_QUERIES);
    expect(answers.p600).toBeUndefined();
  });

  it("answers nothing, rather than throwing, without a bridge", async () => {
    await expect(fetchPlatformSupport(queries(3))).resolves.toEqual({});
  });
});

describe("fetchPlatformSupport — the per-platform fallback", () => {
  it("falls back on a shell that predates the bulk method", async () => {
    const getPlatformSupport = vi
      .fn()
      .mockResolvedValue({ supported: true, emulator: "PCSX2" });
    installBridge({ getPlatformSupport });

    const answers = await fetchPlatformSupport(queries(3));

    expect(getPlatformSupport).toHaveBeenCalledTimes(3);
    expect(answers.p0).toEqual({ supported: true, emulator: "PCSX2" });
  });

  // One call per platform, so a large library would otherwise open one
  // renderer-to-main call per platform at once.
  it("bounds how many it has in flight at once", async () => {
    let inFlight = 0;
    let peak = 0;
    const getPlatformSupport = vi.fn().mockImplementation(async () => {
      inFlight += 1;
      peak = Math.max(peak, inFlight);
      await Promise.resolve();
      inFlight -= 1;
      return { supported: false };
    });
    installBridge({ getPlatformSupport });

    await fetchPlatformSupport(queries(1100));

    expect(peak).toBeLessThanOrEqual(MAX_PLATFORM_QUERIES);
  });

  it("loses only the platform that could not be answered", async () => {
    const getPlatformSupport = vi
      .fn()
      .mockRejectedValueOnce(new Error("no"))
      .mockResolvedValue({ supported: true, emulator: "RetroArch" });
    installBridge({ getPlatformSupport });

    const answers = await fetchPlatformSupport(queries(3));

    expect(answers.p0).toBeUndefined();
    expect(Object.keys(answers)).toHaveLength(2);
  });
});

describe("cancelNative", () => {
  it("reports a request the shell never received", async () => {
    installBridge({});
    await expect(cancelNative(1)).resolves.toBe(false);
  });

  it("reports a request the shell threw on", async () => {
    installBridge({ cancel: vi.fn().mockRejectedValue(new Error("nope")) });
    await expect(cancelNative(1)).resolves.toBe(false);
  });

  // Delivery, not acceptance: the shell's cancel returns silently both when it
  // knows no such launch and when the emulator has already started.
  it("reports delivery when the shell takes the request", async () => {
    installBridge({ cancel: vi.fn().mockResolvedValue(undefined) });
    await expect(cancelNative(1)).resolves.toBe(true);
  });
});

describe("openNativeSettings", () => {
  it("answers false when the shell has no settings to open", async () => {
    installBridge({});
    await expect(openNativeSettings()).resolves.toBe(false);
  });

  it("answers false when the shell could not open them", async () => {
    installBridge({
      openSettings: vi.fn().mockRejectedValue(new Error("unwritable")),
    });
    await expect(openNativeSettings()).resolves.toBe(false);
  });

  it("answers true once the shell has opened them", async () => {
    installBridge({ openSettings: vi.fn().mockResolvedValue(undefined) });
    await expect(openNativeSettings()).resolves.toBe(true);
  });
});

describe("nativeErrorMessage", () => {
  // A LaunchFailure crossing the context bridge is a plain object, not an
  // Error, and String() would render it as "[object Object]".
  it("reads the message off a rejection that is not an Error", () => {
    expect(
      nativeErrorMessage({ code: "launch-failed", message: "no core" }),
    ).toBe("no core");
  });

  it("reads the message off an Error", () => {
    expect(nativeErrorMessage(new Error("boom"))).toBe("boom");
  });

  it("falls back to the value itself when there is no message", () => {
    expect(nativeErrorMessage("plain")).toBe("plain");
  });
});
