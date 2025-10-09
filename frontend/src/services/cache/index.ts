// trunk-ignore-all(eslint/@typescript-eslint/no-explicit-any)
import { useLocalStorage } from "@vueuse/core";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import api from "@/services/api";

interface CacheEntry {
  data: unknown;
}

class CacheService {
  private cache: Cache | null = null;
  private pendingRequests = new Map<string, Promise<AxiosResponse>>();
  private backgroundCallbacks = new Map<string, (data: any) => void>();
  private readonly CACHE_NAME = "romm-api-cache";
  private enableExperimentalCache = useLocalStorage(
    "settings.enableExperimentalCache",
    false,
  );

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
    const { url, params } = config;
    const queryString = params ? new URLSearchParams(params).toString() : "";

    return `${window.location.origin}${url}${queryString ? `?${queryString}` : ""}`;
  }

  private async getCachedResponse(
    cacheKey: string,
  ): Promise<CacheEntry | null> {
    if (!this.cache) return null;

    try {
      const response = await this.cache.match(cacheKey);
      if (!response) return null;

      return await response.json();
    } catch (error) {
      console.error("Error reading from cache:", error);
      return null;
    }
  }

  private async setCachedResponse(
    cacheKey: string,
    data: unknown,
  ): Promise<void> {
    if (!this.cache) return;

    try {
      const response = new Response(JSON.stringify({ data }), {
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
    onBackgroundUpdate: (data: T) => void,
  ): Promise<AxiosResponse<T>> {
    // If experimental cache is disabled, make direct API call
    if (!this.enableExperimentalCache.value) {
      return api.request<T>(config);
    }

    const cacheKey = this.generateCacheKey(config);

    // Check if there's already a pending request for this cache key
    if (this.pendingRequests.has(cacheKey)) {
      return this.pendingRequests.get(cacheKey)!;
    }

    // Check cache first
    const cachedEntry = await this.getCachedResponse(cacheKey);
    if (cachedEntry) {
      this.backgroundCallbacks.set(cacheKey, onBackgroundUpdate);

      // Trigger background update
      this.makeRequest<T>(cacheKey, config);
      return {
        data: cachedEntry.data,
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      } as AxiosResponse<T>;
    }

    // Make the actual request if no cache hit
    const requestPromise = this.makeRequest<T>(cacheKey, config);
    this.pendingRequests.set(cacheKey, requestPromise);

    try {
      return await requestPromise;
    } finally {
      this.pendingRequests.delete(cacheKey);
    }
  }

  private async makeRequest<T = unknown>(
    cacheKey: string,
    config: AxiosRequestConfig,
  ): Promise<AxiosResponse<T>> {
    const response = await api.request<T>(config);

    // Only cache successful responses
    if (response.status >= 200 && response.status < 300) {
      await this.setCachedResponse(cacheKey, response.data);
    }

    // Trigger the registered callback
    const callback = this.backgroundCallbacks.get(cacheKey);
    if (callback) {
      try {
        callback(response.data);
      } catch (error) {
        console.error("Error in background update callback:", error);
      } finally {
        this.backgroundCallbacks.delete(cacheKey);
      }
    }

    return response;
  }

  async clearCache(): Promise<void> {
    if (!this.cache) return;

    try {
      await caches.delete(this.CACHE_NAME);
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
