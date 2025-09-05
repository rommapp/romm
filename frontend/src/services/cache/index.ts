import type { AxiosRequestConfig, AxiosResponse } from "axios";
import api from "@/services/api";
import type { CacheConfig } from "./api";

interface CacheEntry {
  data: unknown;
  timestamp: number;
  ttl: number;
  etag?: string;
}

class CacheService {
  private cache: Cache | null = null;
  private pendingRequests = new Map<string, Promise<AxiosResponse>>();
  private readonly CACHE_NAME = "romm-api-cache";
  private readonly DEFAULT_TTL = 5 * 60 * 1000; // 5 minutes

  async init(): Promise<void> {
    if (!("caches" in window)) {
      console.warn("Cache API not supported, falling back to memory cache");
      return;
    }

    try {
      this.cache = await caches.open(this.CACHE_NAME);
    } catch (error) {
      console.error("Failed to open cache:", error);
    }
  }

  private generateCacheKey(config: AxiosRequestConfig): string {
    const { url, params, data } = config;
    const baseUrl = url || "";
    const queryString = params ? new URLSearchParams(params).toString() : "";
    const dataString = data ? JSON.stringify(data) : "";

    return `${window.location.origin}${baseUrl}${queryString ? `?${queryString}` : ""}${dataString ? `:${dataString}` : ""}`;
  }

  private async getCachedResponse(
    cacheKey: string,
  ): Promise<CacheEntry | null> {
    if (!this.cache) return null;

    try {
      const response = await this.cache.match(cacheKey);
      if (!response) return null;

      const cacheEntry: CacheEntry = await response.json();
      const now = Date.now();

      // Check if cache entry is expired
      if (now - cacheEntry.timestamp > cacheEntry.ttl) {
        await this.cache.delete(cacheKey);
        return null;
      }

      return cacheEntry;
    } catch (error) {
      console.error("Error reading from cache:", error);
      return null;
    }
  }

  private async setCachedResponse(
    cacheKey: string,
    data: unknown,
    config: CacheConfig = {},
  ): Promise<void> {
    if (!this.cache) return;

    try {
      const ttl = config.ttl || this.DEFAULT_TTL;
      const cacheEntry: CacheEntry = {
        data,
        timestamp: Date.now(),
        ttl,
      };

      const response = new Response(JSON.stringify(cacheEntry), {
        headers: {
          "Content-Type": "application/json",
        },
      });

      await this.cache.put(cacheKey, response);
    } catch (error) {
      console.error("Error writing to cache:", error);
    }
  }

  async request<T = unknown>(
    config: AxiosRequestConfig,
    cacheConfig: CacheConfig = {},
  ): Promise<AxiosResponse<T>> {
    const cacheKey = this.generateCacheKey(config);

    // Check if there's already a pending request for this cache key
    if (this.pendingRequests.has(cacheKey)) {
      return this.pendingRequests.get(cacheKey)!;
    }

    // Check cache first
    const cachedEntry = await this.getCachedResponse(cacheKey);

    if (cachedEntry) {
      // Always return cached data immediately and refetch in background
      this.updateInBackground(config, cacheConfig);
      return {
        data: cachedEntry.data,
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      } as AxiosResponse<T>;
    }

    // Make the actual request
    const requestPromise = this.makeRequest<T>(config, cacheConfig);
    this.pendingRequests.set(cacheKey, requestPromise);

    try {
      return await requestPromise;
    } finally {
      this.pendingRequests.delete(cacheKey);
    }
  }

  private async makeRequest<T = unknown>(
    config: AxiosRequestConfig,
    cacheConfig: CacheConfig = {},
  ): Promise<AxiosResponse<T>> {
    const response = await api.request<T>(config);

    // Cache successful responses
    if (response.status >= 200 && response.status < 300) {
      const cacheKey = this.generateCacheKey(config);
      await this.setCachedResponse(cacheKey, response.data, cacheConfig);
    }

    return response;
  }

  private async updateInBackground(
    config: AxiosRequestConfig,
    cacheConfig: CacheConfig = {},
  ): Promise<void> {
    try {
      const response = await api.request(config);

      if (response.status >= 200 && response.status < 300) {
        const cacheKey = this.generateCacheKey(config);
        await this.setCachedResponse(cacheKey, response.data, cacheConfig);
      }
    } catch (error) {
      console.error("Background update failed:", error);
    }
  }

  async clearCache(): Promise<void> {
    if (!this.cache) return;

    try {
      await this.cache.delete(this.CACHE_NAME);
      this.cache = await caches.open(this.CACHE_NAME);
    } catch (error) {
      console.error("Error clearing cache:", error);
    }
  }

  async clearCacheForPattern(pattern: string): Promise<void> {
    if (!this.cache) return;

    try {
      const keys = await this.cache.keys();
      const matchingKeys = keys.filter((key) => key.url.includes(pattern));

      await Promise.all(matchingKeys.map((key) => this.cache!.delete(key)));
    } catch (error) {
      console.error("Error clearing cache pattern:", error);
    }
  }

  async getCacheSize(): Promise<number> {
    if (!this.cache) return 0;

    try {
      const keys = await this.cache.keys();
      return keys.length;
    } catch (error) {
      console.error("Error getting cache size:", error);
      return 0;
    }
  }
}

const cacheService = new CacheService();

cacheService.init();

export default cacheService;
