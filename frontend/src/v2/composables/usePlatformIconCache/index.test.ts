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
  it("fetches the shipped .ico when the platform ships no .svg", async () => {
    respondWith({ "/assets/platforms/saturn.ico": "image/x-icon" });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["saturn"]);
    await settle();

    expect(urls()).toEqual(["/assets/platforms/saturn.ico"]);
    expect(getCachedPlatformIcon("saturn")).toBe("blob:cached");
  });

  it("fetches only the .svg when both variants ship", async () => {
    respondWith({ "/assets/platforms/dc.svg": "image/svg+xml" });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(urls()).toEqual(["/assets/platforms/dc.svg"]);
    expect(getCachedPlatformIcon("dc")).toBe("blob:cached");
  });

  it("caches nothing when the response is not an image", async () => {
    respondWith({ "/assets/platforms/dc.svg": "text/html" });
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(getCachedPlatformIcon("dc")).toBeUndefined();
  });

  it("caches nothing when the fetch fails in transport", async () => {
    fetchMock.mockRejectedValue(new Error("connection reset"));
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["dc"]);
    await settle();

    expect(getCachedPlatformIcon("dc")).toBeUndefined();
  });

  it("does not request a platform that ships no icon", async () => {
    respondWith({});
    const { prefetchPlatformIcons, getCachedPlatformIcon } = await load();

    prefetchPlatformIcons(["singe"]);
    await settle();

    expect(urls()).toEqual([]);
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
