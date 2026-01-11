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
      platform_ids:
        params.platformIds && params.platformIds.length > 0
          ? params.platformIds
          : undefined,
      collection_id: params.collectionId,
      virtual_collection_id: params.virtualCollectionId,
      smart_collection_id: params.smartCollectionId,
      search_term: params.searchTerm,
      limit: params.limit,
      offset: params.offset,
      order_by: params.orderBy,
      order_dir: params.orderDir,
      group_by_meta_id: params.groupByMetaId,
      genres:
        params.selectedGenres && params.selectedGenres.length > 0
          ? params.selectedGenres
          : undefined,
      franchises:
        params.selectedFranchises && params.selectedFranchises.length > 0
          ? params.selectedFranchises
          : undefined,
      collections:
        params.selectedCollections && params.selectedCollections.length > 0
          ? params.selectedCollections
          : undefined,
      companies:
        params.selectedCompanies && params.selectedCompanies.length > 0
          ? params.selectedCompanies
          : undefined,
      age_ratings:
        params.selectedAgeRatings && params.selectedAgeRatings.length > 0
          ? params.selectedAgeRatings
          : undefined,
      selected_statuses:
        params.selectedStatuses && params.selectedStatuses.length > 0
          ? params.selectedStatuses
          : undefined,
      regions:
        params.selectedRegions && params.selectedRegions.length > 0
          ? params.selectedRegions
          : undefined,
      languages:
        params.selectedLanguages && params.selectedLanguages.length > 0
          ? params.selectedLanguages
          : undefined,
      player_counts:
        params.selectedPlayerCounts && params.selectedPlayerCounts.length > 0
          ? params.selectedPlayerCounts
          : undefined,
      // Logic operators
      genres_logic:
        params.selectedGenres && params.selectedGenres.length > 1
          ? params.genresLogic || "any"
          : undefined,
      franchises_logic:
        params.selectedFranchises && params.selectedFranchises.length > 1
          ? params.franchisesLogic || "any"
          : undefined,
      collections_logic:
        params.selectedCollections && params.selectedCollections.length > 1
          ? params.collectionsLogic || "any"
          : undefined,
      companies_logic:
        params.selectedCompanies && params.selectedCompanies.length > 1
          ? params.companiesLogic || "any"
          : undefined,
      age_ratings_logic:
        params.selectedAgeRatings && params.selectedAgeRatings.length > 1
          ? params.ageRatingsLogic || "any"
          : undefined,
      regions_logic:
        params.selectedRegions && params.selectedRegions.length > 1
          ? params.regionsLogic || "any"
          : undefined,
      languages_logic:
        params.selectedLanguages && params.selectedLanguages.length > 1
          ? params.languagesLogic || "any"
          : undefined,
      statuses_logic:
        params.selectedStatuses && params.selectedStatuses.length > 1
          ? params.statusesLogic || "any"
          : undefined,
      player_counts_logic:
        params.selectedPlayerCounts && params.selectedPlayerCounts.length > 1
          ? params.playerCountsLogic || "any"
          : undefined,
      ...(params.filterMatched !== null
        ? { matched: params.filterMatched }
        : {}),
      ...(params.filterFavorites !== null
        ? { favorite: params.filterFavorites }
        : {}),
      ...(params.filterDuplicates !== null
        ? { duplicate: params.filterDuplicates }
        : {}),
      ...(params.filterPlayables !== null
        ? { playable: params.filterPlayables }
        : {}),
      ...(params.filterMissing !== null
        ? { missing: params.filterMissing }
        : {}),
      ...(params.filterRA !== null ? { has_ra: params.filterRA } : {}),
      ...(params.filterVerified !== null
        ? { verified: params.filterVerified }
        : {}),
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
      last_played: true,
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
      last_played: true,
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
