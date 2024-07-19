/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */

export type ConfigResponse = {
  EXCLUDED_PLATFORMS: Array<string>;
  EXCLUDED_SINGLE_EXT: Array<string>;
  EXCLUDED_SINGLE_FILES: Array<string>;
  EXCLUDED_MULTI_FILES: Array<string>;
  EXCLUDED_MULTI_PARTS_EXT: Array<string>;
  EXCLUDED_MULTI_PARTS_FILES: Array<string>;
  PLATFORMS_BINDING: Record<string, string>;
  PLATFORMS_VERSIONS: Record<string, string>;
  ROMS_FOLDER_NAME: string;
  FIRMWARE_FOLDER_NAME: string;
  HIGH_PRIO_STRUCTURE_PATH: string;
};
