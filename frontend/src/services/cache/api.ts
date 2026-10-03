// trunk-ignore-all(eslint/@typescript-eslint/no-explicit-any)
import type { AxiosRequestConfig, AxiosResponse, Method } from "axios";
import type { CustomLimitOffsetPage_SimpleRomSchema_ as GetRomsResponse } from "@/__generated__/models/CustomLimitOffsetPage_SimpleRomSchema_";
import { buildGetRomsQuery, type GetRomsParams } from "@/services/api/rom";
import cacheService from "@/services/cache";

// The home rows render a fixed number of covers and never show a total, so they
// opt out of the whole-library count. Each map is shared by the request and its
// cache-clear pattern: the pattern is matched against the cache key by
// substring, so a parameter present on one side but not the other would leave
// the row permanently stale.
const RECENT_ROMS_PARAMS = {
  order_by: "id",
  order_dir: "desc",
  limit: 15,
  with_char_index: false,
  with_filter_values: false,
  with_rom_id_index: false,
  with_total: false,
} as const;

const RECENT_PLAYED_ROMS_PARAMS = {
  order_by: "last_played",
  order_dir: "desc",
  limit: 15,
  with_char_index: false,
  with_filter_values: false,
  with_rom_id_index: false,
  with_total: false,
  last_played: true,
} as const;

class CachedApiService {
  private createRequestConfig(
    method: Method,
    url: string,
    params?: any,
  ): AxiosRequestConfig {
    return {
      method,
      url,
      params,
    };
  }

  async getRoms(
    params: GetRomsParams,
    onBackgroundUpdate: (data: GetRomsResponse) => void,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig(
      "GET",
      "/roms",
      buildGetRomsQuery(params),
    );

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  async getRecentRoms(
    onBackgroundUpdate: (data: GetRomsResponse) => void,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig("GET", "/roms", RECENT_ROMS_PARAMS);

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  async getRecentPlayedRoms(
    onBackgroundUpdate: (data: GetRomsResponse) => void,
  ): Promise<AxiosResponse<GetRomsResponse>> {
    const config = this.createRequestConfig(
      "GET",
      "/roms",
      RECENT_PLAYED_ROMS_PARAMS,
    );

    return cacheService.request<GetRomsResponse>(config, onBackgroundUpdate);
  }

  private async clearRomsCache(params: any) {
    const queryString = params ? new URLSearchParams(params).toString() : "";
    await cacheService.clearCacheForPattern(`/roms?${queryString}`);
  }

  async clearRecentRomsCache() {
    await this.clearRomsCache(RECENT_ROMS_PARAMS);
  }

  async clearRecentPlayedRomsCache() {
    await this.clearRomsCache(RECENT_PLAYED_ROMS_PARAMS);
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
