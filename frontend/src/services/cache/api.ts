import type { AxiosRequestConfig, AxiosResponse } from "axios";
import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema } from "@/__generated__/";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import type { GetRomsParams } from "@/services/api/rom";
import cacheService from "@/services/cache";
import { getStatusKeyForText } from "@/utils";

export interface CacheConfig {
  ttl?: number;
  staleWhileRevalidate?: boolean;
}

// Cache configurations for different types of requests
const CACHE_CONFIGS: Record<string, CacheConfig> = {
  // ROMs data - cache for 5 minutes, allow stale for 30 minutes
  roms: {
    ttl: 5 * 60 * 1000, // 5 minutes
    staleWhileRevalidate: true,
  },
  // Recent ROMs - cache for 2 minutes, allow stale for 10 minutes
  recentRoms: {
    ttl: 2 * 60 * 1000, // 2 minutes
    staleWhileRevalidate: true,
  },
  // Individual ROM details - cache for 10 minutes, allow stale for 1 hour
  romDetails: {
    ttl: 10 * 60 * 1000, // 10 minutes
    staleWhileRevalidate: true,
  },
  // Search results - cache for 1 minute, no stale while revalidate
  search: {
    ttl: 1 * 60 * 1000, // 1 minute
  },
  // Platform/collection data - cache for 15 minutes, allow stale for 2 hours
  metadata: {
    ttl: 15 * 60 * 1000, // 15 minutes
    staleWhileRevalidate: true,
  },
};

class CachedApiService {
  private getCacheConfig(
    endpoint: string,
    params?: GetRomsParams,
  ): CacheConfig {
    // Determine cache strategy based on endpoint and parameters
    if (endpoint.includes("/roms") && !endpoint.includes("/search")) {
      if (params?.searchTerm) {
        return CACHE_CONFIGS.search;
      }
      if (params?.orderBy === "id" || params?.orderBy === "last_played") {
        return CACHE_CONFIGS.recentRoms;
      }
      return CACHE_CONFIGS.roms;
    }

    if (endpoint.includes("/search")) {
      return CACHE_CONFIGS.search;
    }

    if (endpoint.match(/\/roms\/\d+$/)) {
      return CACHE_CONFIGS.romDetails;
    }

    return CACHE_CONFIGS.metadata;
  }

  private createRequestConfig(
    method: string,
    url: string,
    params?: unknown,
    data?: unknown,
    headers?: Record<string, string>,
  ): AxiosRequestConfig {
    return {
      method: method as "GET" | "POST" | "PUT" | "DELETE" | "PATCH",
      url,
      params,
      data,
      headers,
    };
  }

  async getRoms(
    params: GetRomsParams,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      platform_id: params.platformId,
      collection_id: params.collectionId,
      virtual_collection_id: params.virtualCollectionId,
      smart_collection_id: params.smartCollectionId,
      search_term: params.searchTerm,
      limit: params.limit,
      offset: params.offset,
      order_by: params.orderBy,
      order_dir: params.orderDir,
      group_by_meta_id: params.groupByMetaId,
      selected_genre: params.selectedGenre,
      selected_franchise: params.selectedFranchise,
      selected_collection: params.selectedCollection,
      selected_company: params.selectedCompany,
      selected_age_rating: params.selectedAgeRating,
      selected_status: getStatusKeyForText(params.selectedStatus ?? null),
      selected_region: params.selectedRegion,
      selected_language: params.selectedLanguage,
      ...(params.filterUnmatched ? { matched: false } : {}),
      ...(params.filterMatched ? { matched: true } : {}),
      ...(params.filterFavourites ? { favourite: true } : {}),
      ...(params.filterDuplicates ? { duplicate: true } : {}),
      ...(params.filterPlayables ? { playable: true } : {}),
      ...(params.filterMissing ? { missing: true } : {}),
      ...(params.filterRA ? { has_ra: true } : {}),
      ...(params.filterVerified ? { verified: true } : {}),
    });
    const cacheConfig = this.getCacheConfig("/roms", params);

    return cacheService.request<GetRomsResponse>(config, cacheConfig);
  }

  async getRecentRoms(): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "id",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });
    const cacheConfig = this.getCacheConfig("/roms", { orderBy: "id" });

    return cacheService.request<GetRomsResponse>(config, cacheConfig);
  }

  async getRecentPlayedRoms(): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "last_played",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });
    const cacheConfig = this.getCacheConfig("/roms", {
      orderBy: "last_played",
    });

    return cacheService.request<GetRomsResponse>(config, cacheConfig);
  }

  async getRom(romId: number): Promise<AxiosResponse<DetailedRomSchema>> {
    const config = this.createRequestConfig("GET", `/roms/${romId}`);
    const cacheConfig = this.getCacheConfig(`/roms/${romId}`);

    return cacheService.request<DetailedRomSchema>(config, cacheConfig);
  }

  async searchRom(params: {
    romId: number;
    searchTerm: string;
    searchBy: string;
  }): Promise<AxiosResponse<SearchRomSchema[]>> {
    const config = this.createRequestConfig("GET", "/search/roms", {
      rom_id: params.romId,
      search_term: params.searchTerm,
      search_by: params.searchBy,
    });
    const cacheConfig = this.getCacheConfig("/search/roms", params);

    return cacheService.request<SearchRomSchema[]>(config, cacheConfig);
  }

  // Non-cached methods (write operations)
  async updateRom(romId: number, data: unknown, params?: unknown) {
    const config = this.createRequestConfig(
      "PUT",
      `/roms/${romId}`,
      params,
      data,
    );

    // Don't cache write operations, but clear related cache entries
    const response = await cacheService.request(config, { ttl: 0 });

    // Clear related cache entries
    await this.clearRelatedCache(romId);

    return response;
  }

  async updateUserRomProps(romId: number, data: unknown, params?: unknown) {
    const config = this.createRequestConfig(
      "PUT",
      `/roms/${romId}/props`,
      params,
      data,
    );

    const response = await cacheService.request(config, { ttl: 0 });

    // Clear related cache entries
    await this.clearRelatedCache(romId);

    return response;
  }

  async deleteRoms(data: unknown) {
    const config = this.createRequestConfig(
      "POST",
      "/roms/delete",
      undefined,
      data,
    );

    const response = await cacheService.request(config, { ttl: 0 });

    // Clear all ROMs cache since we don't know which specific ROMs were deleted
    await this.clearAllRomsCache();

    return response;
  }

  async uploadRoms(
    platformId: number,
    formData: FormData,
    headers: Record<string, string>,
  ) {
    const config = this.createRequestConfig(
      "POST",
      "/roms",
      undefined,
      formData,
      {
        "Content-Type": "multipart/form-data",
        ...headers,
      },
    );

    const response = await cacheService.request(config, { ttl: 0 });

    // Clear platform-specific cache
    await this.clearPlatformCache(platformId);

    return response;
  }

  private async clearRelatedCache(romId: number) {
    // Clear individual ROM cache
    await cacheService.clearCacheForPattern(`/roms/${romId}`);

    // Clear ROMs list cache (since the ROM might have been updated)
    await cacheService.clearCacheForPattern("/roms");
  }

  private async clearPlatformCache(platformId: number) {
    // Clear platform-specific ROMs cache
    await cacheService.clearCacheForPattern(`platform_id=${platformId}`);
  }

  private async clearAllRomsCache() {
    // Clear all ROMs-related cache
    await cacheService.clearCacheForPattern("/roms");
  }

  // Cache management methods
  async clearCache() {
    return cacheService.clearCache();
  }

  async getCacheSize() {
    return cacheService.getCacheSize();
  }

  async clearCacheForPattern(pattern: string) {
    return cacheService.clearCacheForPattern(pattern);
  }
}

// Create singleton instance
const cachedApiService = new CachedApiService();

export default cachedApiService;
