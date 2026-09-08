import type { AxiosRequestConfig, AxiosResponse } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  RECENT_PLAYED_ROMS_LIMIT,
  RECENT_ROMS_LIMIT,
} from "@/services/api/rom";
import cacheService from "@/services/cache";
import cachedApiService from "@/services/cache/api";

vi.mock("@/services/cache", () => ({
  default: {
    request: vi.fn(),
    clearCacheForPattern: vi.fn(),
    clearCache: vi.fn(),
    getCacheSize: vi.fn(),
  },
}));

const noop = () => undefined;

// Mirrors CacheService.generateCacheKey, so the assertions below exercise the
// same string the real cache stores entries under.
function cacheKeyFor(params: AxiosRequestConfig["params"]): string {
  const queryString = params ? new URLSearchParams(params).toString() : "";
  return `${window.location.origin}/roms${queryString ? `?${queryString}` : ""}`;
}

function requestParams(callIndex = 0): AxiosRequestConfig["params"] {
  return vi.mocked(cacheService.request).mock.calls[callIndex][0].params;
}

function clearedPattern(callIndex = 0): string {
  return vi.mocked(cacheService.clearCacheForPattern).mock.calls[callIndex][0];
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(cacheService.request).mockResolvedValue({
    data: { items: [] },
  } as AxiosResponse);
  vi.mocked(cacheService.clearCacheForPattern).mockResolvedValue(undefined);
});

describe("home row requests", () => {
  it("does not make the server count the library for recently added", async () => {
    await cachedApiService.getRecentRoms(noop);

    expect(requestParams()).toMatchObject({
      limit: RECENT_ROMS_LIMIT,
      with_total: false,
    });
  });

  it("does not make the server count the library for recently played", async () => {
    await cachedApiService.getRecentPlayedRoms(noop);

    expect(requestParams()).toMatchObject({
      limit: RECENT_PLAYED_ROMS_LIMIT,
      with_total: false,
    });
  });
});

describe("home row cache invalidation", () => {
  // The clear patterns repeat the request's parameter map, and
  // clearCacheForPattern matches by substring. Any parameter added to one side
  // but not the other, or added in a different position, silently stops the row
  // from ever being invalidated.
  it("clears the entry recently added actually wrote", async () => {
    await cachedApiService.getRecentRoms(noop);
    await cachedApiService.clearRecentRomsCache();

    expect(cacheKeyFor(requestParams())).toContain(clearedPattern());
  });

  it("clears the entry recently played actually wrote", async () => {
    await cachedApiService.getRecentPlayedRoms(noop);
    await cachedApiService.clearRecentPlayedRomsCache();

    expect(cacheKeyFor(requestParams())).toContain(clearedPattern());
  });
});
