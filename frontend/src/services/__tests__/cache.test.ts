import { describe, it, expect, beforeEach, vi } from "vitest";
import cacheService from "@/services/cache";

// Mock the Cache API
const mockCache = {
  match: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  keys: vi.fn(),
};

const mockCaches = {
  open: vi.fn().mockResolvedValue(mockCache),
};

// Mock global caches
Object.defineProperty(global, "caches", {
  value: mockCaches,
  writable: true,
});

describe("CacheService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCache.match.mockResolvedValue(null);
    mockCache.put.mockResolvedValue(undefined);
    mockCache.delete.mockResolvedValue(true);
    mockCache.keys.mockResolvedValue([]);
  });

  it("should initialize cache on module load", async () => {
    expect(mockCaches.open).toHaveBeenCalledWith("romm-api-cache");
  });

  it("should handle cache miss gracefully", async () => {
    mockCache.match.mockResolvedValue(null);

    const result = await cacheService.getCacheSize();
    expect(result).toBe(0);
  });

  it("should clear cache successfully", async () => {
    mockCache.keys.mockResolvedValue([
      { url: "http://localhost/api/roms" },
      { url: "http://localhost/api/platforms" },
    ]);

    await cacheService.clearCache();

    expect(mockCache.delete).toHaveBeenCalledWith("romm-api-cache");
  });

  it("should clear cache for specific pattern", async () => {
    const mockKeys = [
      { url: "http://localhost/api/roms?platform_id=1" },
      { url: "http://localhost/api/roms?platform_id=2" },
      { url: "http://localhost/api/platforms" },
    ];

    mockCache.keys.mockResolvedValue(mockKeys);

    await cacheService.clearCacheForPattern("platform_id=1");

    expect(mockCache.delete).toHaveBeenCalledWith(mockKeys[0]);
    expect(mockCache.delete).not.toHaveBeenCalledWith(mockKeys[1]);
    expect(mockCache.delete).not.toHaveBeenCalledWith(mockKeys[2]);
  });
});
