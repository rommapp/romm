import type {
  SetupLibraryResponse,
  SetupPlatformsResponse,
} from "@/__generated__";
import api from "@/services/api";

/** @deprecated Import `SetupLibraryResponse` from `@/__generated__`. */
export type SetupLibraryInfo = SetupLibraryResponse;

export default {
  async getLibraryInfo() {
    return await api.get<SetupLibraryResponse>("/setup/library");
  },

  async createPlatforms(platformSlugs: string[]) {
    return await api.post<SetupPlatformsResponse>(
      "/setup/platforms",
      platformSlugs,
    );
  },
};
