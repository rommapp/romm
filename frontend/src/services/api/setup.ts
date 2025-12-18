import api from "@/services/api";
import type { Platform } from "@/stores/platforms";

export type LibraryStructure = "A" | "B" | null;

export interface SetupLibraryInfo {
  detected_structure: LibraryStructure;
  existing_platforms: string[];
  supported_platforms: Platform[];
}

export interface CreatePlatformsResponse {
  success: boolean;
  created_count: number;
  message: string;
}

export default {
  async getLibraryInfo() {
    return await api.get<SetupLibraryInfo>("/setup/library");
  },

  async createPlatforms(platformSlugs: string[]) {
    return await api.post<CreatePlatformsResponse>(
      "/setup/platforms",
      platformSlugs,
    );
  },
};
