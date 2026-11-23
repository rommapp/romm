/* generated using openapi-typescript-codegen -- do not edit */
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
    /**
     * Whether the user chose this version as the main one of its game.
     */
    is_main_sibling: boolean;
    backlogged: boolean;
    now_playing: boolean;
    hidden: boolean;
    /**
     * The user's rating, from 0 to 10. 0 means unset.
     */
    rating: number;
    /**
     * The user's difficulty rating, from 0 to 10. 0 means unset.
     */
    difficulty: number;
    /**
     * The user's completion percentage, from 0 to 100. 0 means unset.
     */
    completion: number;
    status: (RomUserStatus | null);
    /**
     * The media keys pinned on the overview, in order. Null means the default selection.
     */
    pinned_media: (Array<string> | null);
};

