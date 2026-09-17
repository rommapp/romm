import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

class FakeURL extends URL {
  static createObjectURL = vi.fn(() => "blob:cached");
  static revokeObjectURL = vi.fn();
}

let fetchMock: ReturnType<typeof vi.fn>;

async function load() {
  vi.resetModules();
  return import("./index");
}

// `prefetchPlatformIcons` runs through `requestIdleCallback` when the
// environment has one and `setTimeout(0)` otherwise, so settle both.
async function settle() {
  await flushPromises();
  await new Promise((resolve) => setTimeout(resolve, 0));
  await flushPromises();
}

function urls() {
  return fetchMock.mock.calls.map((call) => call[0]);
}

function respondWith(available: Record<string, string>) {
  fetchMock.mockImplementation(async (url: string) => {
    const type = available[url];
    return {
      ok: Boolean(type),
      blob: async () => new Blob([type ?? ""], { type: type ?? "" }),
    };
  });
}

beforeEach(() => {
  vi.stubGlobal("URL", FakeURL);
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

describe("prefetchPlatformIcons", () => {
  it("falls back to .ico when the platform ships no .svg", async () => {
    respondWith({ "/assets/platforms/saturn.ico": "image/x-icon" });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["saturn"]);
    await settle();

    expect(urls()).toEqual([
      "/assets/platforms/saturn.svg",
      "/assets/platforms/saturn.ico",
    ]);
    expect(getCachedPlatformIcon("saturn")).toBe("blob:cached");
  });

  it("stops at .svg when that variant resolves", async () => {
    respondWith({ "/assets/platforms/dc.svg": "image/svg+xml" });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(urls()).toEqual(["/assets/platforms/dc.svg"]);
    expect(getCachedPlatformIcon("dc")).toBe("blob:cached");
  });

  it("ignores a non-image body and keeps probing", async () => {
    respondWith({
      "/assets/platforms/dc.svg": "text/html",
      "/assets/platforms/dc.ico": "image/x-icon",
    });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(urls()).toEqual([
      "/assets/platforms/dc.svg",
      "/assets/platforms/dc.ico",
    ]);
    expect(getCachedPlatformIcon("dc")).toBe("blob:cached");
  });

  it("keeps probing after a candidate fails in transport", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith(".svg")) throw new Error("connection reset");
      return {
        ok: true,
        blob: async () => new Blob(["x"], { type: "image/x-icon" }),
      };
    });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["saturn"]);
    await settle();

    expect(urls()).toEqual([
      "/assets/platforms/saturn.svg",
      "/assets/platforms/saturn.ico",
    ]);
    expect(getCachedPlatformIcon("saturn")).toBe("blob:cached");
  });

  it("caches nothing for a platform with no asset at all", async () => {
    respondWith({});
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["singe"]);
    await settle();

    expect(urls()).toEqual([
      "/assets/platforms/singe.svg",
      "/assets/platforms/singe.ico",
    ]);
    expect(getCachedPlatformIcon("singe")).toBeUndefined();
  });

  it("does not re-fetch a slug it already cached", async () => {
    respondWith({ "/assets/platforms/dc.svg": "image/svg+xml" });
    const { prefetchPlatformIcons } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();
    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(urls()).toEqual(["/assets/platforms/dc.svg"]);
  });

  it("normalizes the slug to lower case", async () => {
    respondWith({ "/assets/platforms/dc.svg": "image/svg+xml" });
    const { prefetchPlatformIcons } = await load();

    prefetchPlatformIcons(["DC"]);
    await settle();

    expect(urls()).toEqual(["/assets/platforms/dc.svg"]);
  });
});
