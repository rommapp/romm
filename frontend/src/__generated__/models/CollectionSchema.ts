/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */

export type CollectionSchema = {
  id: number;
  name: string;
  description: string;
  path_cover_l: string | null;
  path_cover_s: string | null;
  has_cover: boolean;
  url_cover: string;
  roms: Array<number>;
  rom_count: number;
  user_id: number;
  user__username: string;
  is_public: boolean;
  created_at: string;
  updated_at: string;
};
