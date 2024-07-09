/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */

export type RomUserSchema = {
  id: number;
  user_id: number;
  rom_id: number;
  created_at: string;
  updated_at: string;
  note_raw_markdown: string;
  note_is_public: boolean;
  is_main_sibling: boolean;
  user__username: string;
};
