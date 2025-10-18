// trunk-ignore-all(eslint/@typescript-eslint/no-explicit-any)
import type {
  AxiosRequestConfig,
  AxiosResponse,
  AxiosHeaders,
  Method,
} from "axios";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import type { GetRomsParams } from "@/services/api/rom";
import cacheService from "@/services/cache";
import { getStatusKeyForText } from "@/utils";

class CachedApiService {
  private createRequestConfig(
    method: Method,
    url: string,
    params?: any,
    headers?: AxiosHeaders,
  ): AxiosRequestConfig {
    return {
      method,
      url,
      params,
      headers,
    };
  }

  async getRoms(
    params: GetRomsParams,
    onBackgroundUpdate: (data: GetRomsResponse) => void,
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
      ...(params.filterFavorites ? { favorite: true } : {}),
      ...(params.filterDuplicates ? { duplicate: true } : {}),
      ...(params.filterPlayables ? { playable: true } : {}),
      ...(params.filterMissing ? { missing: true } : {}),
      ...(params.filterRA ? { has_ra: true } : {}),
      ...(params.filterVerified ? { verified: true } : {}),
    });

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  async getRecentRoms(
    onBackgroundUpdate: (data: GetRomsResponse) => void,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "id",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  async getRecentPlayedRoms(
    onBackgroundUpdate: (data: GetRomsResponse) => void,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", {
      order_by: "last_played",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  private async clearRomsCache(params: any) {
    const queryString = params ? new URLSearchParams(params).toString() : "";
    await cacheService.clearCacheForPattern(`/roms?${queryString}`);
  }

  async clearRecentRomsCache() {
    await this.clearRomsCache({
      order_by: "id",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });
  }

  async clearRecentPlayedRomsCache() {
    await this.clearRomsCache({
      order_by: "last_played",
      order_dir: "desc",
      limit: 15,
      with_char_index: false,
    });
  }

  // Cache management methods
  async clearCache() {
    return cacheService.clearCache();
  }

  async getCacheSize() {
    return cacheService.getCacheSize();
  }
}

export default new CachedApiService();
