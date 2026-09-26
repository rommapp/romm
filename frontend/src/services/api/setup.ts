import type {
  SetupLibraryResponse,
  SetupPlatformsResponse,
} from "@/__generated__";
import api from "@/services/api";

export type SetupLibraryInfo = SetupLibraryResponse;

export default {
  async getLibraryInfo() {
    return await api.get<SetupLibraryInfo>("/setup/library");
  },

  async createPlatforms(platformSlugs: string[]) {
    return await api.post<SetupPlatformsResponse>(
      "/setup/platforms",
      platformSlugs,
    );
  },
};
