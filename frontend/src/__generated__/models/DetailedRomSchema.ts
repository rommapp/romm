/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */

import type { CollectionSchema } from "./CollectionSchema";
import type { RomIGDBMetadata } from "./RomIGDBMetadata";
import type { RomMobyMetadata } from "./RomMobyMetadata";
import type { RomSchema } from "./RomSchema";
import type { RomUserSchema } from "./RomUserSchema";
import type { SaveSchema } from "./SaveSchema";
import type { ScreenshotSchema } from "./ScreenshotSchema";
import type { StateSchema } from "./StateSchema";
import type { UserNotesSchema } from "./UserNotesSchema";

export type DetailedRomSchema = {
  id: number;
  igdb_id: number | null;
  sgdb_id: number | null;
  moby_id: number | null;
  platform_id: number;
  platform_slug: string;
  platform_name: string;
  file_name: string;
  file_name_no_tags: string;
  file_name_no_ext: string;
  file_extension: string;
  file_path: string;
  file_size_bytes: number;
  name: string | null;
  slug: string | null;
  summary: string | null;
  first_release_date: number | null;
  alternative_names: Array<string>;
  genres: Array<string>;
  franchises: Array<string>;
  collections: Array<string>;
  companies: Array<string>;
  game_modes: Array<string>;
  igdb_metadata: RomIGDBMetadata | null;
  moby_metadata: RomMobyMetadata | null;
  path_cover_s: string | null;
  path_cover_l: string | null;
  has_cover: boolean;
  url_cover: string | null;
  revision: string | null;
  regions: Array<string>;
  languages: Array<string>;
  tags: Array<string>;
  multi: boolean;
  files: Array<string>;
  full_path: string;
  created_at: string;
  updated_at: string;
  rom_user?: RomUserSchema | null;
  merged_screenshots: Array<string>;
  sibling_roms?: Array<RomSchema>;
  user_saves?: Array<SaveSchema>;
  user_states?: Array<StateSchema>;
  user_screenshots?: Array<ScreenshotSchema>;
  user_notes?: Array<UserNotesSchema>;
  user_collections?: Array<CollectionSchema>;
  readonly sort_comparator: string;
};
