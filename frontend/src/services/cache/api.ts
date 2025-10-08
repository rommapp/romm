import type { AxiosRequestConfig, AxiosResponse } from "axios";
import type { SearchRomSchema } from "@/__generated__";
import type { DetailedRomSchema } from "@/__generated__/";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import type { GetRomsParams } from "@/services/api/rom";
import cacheService from "@/services/cache";
import { getStatusKeyForText } from "@/utils";

class CachedApiService {
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

    return cacheService.request<GetRomsResponse>(config);
  }

  async getRecentRoms(): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "id",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });

    return cacheService.request<GetRomsResponse>(config);
  }

  async getRecentPlayedRoms(): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "last_played",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });

    return cacheService.request<GetRomsResponse>(config);
  }

  async getRom(romId: number): Promise<AxiosResponse<DetailedRomSchema>> {
    const config = this.createRequestConfig("GET", `/roms/${romId}`);

    return cacheService.request<DetailedRomSchema>(config);
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

    return cacheService.request<SearchRomSchema[]>(config);
  }

  private async clearRelatedCache(romId: number) {
    await cacheService.clearCacheForPattern(`/roms/${romId}`);
    await cacheService.clearCacheForPattern("/roms");
  }

  private async clearPlatformCache(platformId: number) {
    await cacheService.clearCacheForPattern(`platform_id=${platformId}`);
  }

  private async clearAllRomsCache() {
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
