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
  // Helper function to handle single vs multi-value parameters
  private getFilterArray(
    single: string | null | undefined,
    multi: string[] | null | undefined,
  ): string[] | undefined {
    const result = (() => {
      if (multi && multi.length > 0) return multi;
      if (single) return [single];
      return undefined;
    })();
    // Only log non-empty results to reduce console noise
    if (result) {
      console.log("CachedApiService getFilterArray - result:", result);
    }
    return result;
  }
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
      genre: this.getFilterArray(params.selectedGenre, params.selectedGenres),
      franchise: this.getFilterArray(
        params.selectedFranchise,
        params.selectedFranchises,
      ),
      collection: this.getFilterArray(
        params.selectedCollection,
        params.selectedCollections,
      ),
      company: this.getFilterArray(
        params.selectedCompany,
        params.selectedCompanies,
      ),
      age_rating: this.getFilterArray(
        params.selectedAgeRating,
        params.selectedAgeRatings,
      ),
      selected_status: getStatusKeyForText(params.selectedStatus ?? null),
      region: this.getFilterArray(
        params.selectedRegion,
        params.selectedRegions,
      ),
      language: this.getFilterArray(
        params.selectedLanguage,
        params.selectedLanguages,
      ),
      // Logic operators
      platforms_logic:
        params.platformIds && params.platformIds.length > 1
          ? params.platformsLogic || "any"
          : undefined,
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
      ...(params.filterUnmatched ? { matched: false } : {}),
      ...(params.filterMatched ? { matched: true } : {}),
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
