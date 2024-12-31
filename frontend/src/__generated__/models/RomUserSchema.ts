/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RomUserStatus } from './RomUserStatus';

export type RomUserSchema = {
    id: number;
    user_id: number;
    rom_id: number;
    created_at: string;
    updated_at: string;
    last_played: (string | null);
    note_raw_markdown: string;
    note_is_public: boolean;
    is_main_sibling: boolean;
    backlogged: boolean;
    now_playing: boolean;
    hidden: boolean;
    rating: number;
    difficulty: number;
    completion: number;
    status: (RomUserStatus | null);
    user__username: string;
};

