/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomUserStatus } from './RomUserStatus';
export type RomUserSchema = {
    /**
     * The internal ID of the record.
     */
    id: number;
    /**
     * The ID of the user.
     */
    user_id: number;
    /**
     * The internal ID of the rom.
     */
    rom_id: number;
    /**
     * When the record was created.
     */
    created_at: string;
    /**
     * When the record last changed.
     */
    updated_at: string;
    /**
     * When the user last played the rom.
     */
    last_played: (string | null);
    /**
     * Whether the user chose this version as the main one of its game.
     */
    is_main_sibling: boolean;
    /**
     * Whether the rom is in the user's backlog.
     */
    backlogged: boolean;
    /**
     * Whether the user is playing the rom now.
     */
    now_playing: boolean;
    /**
     * Whether the user hid the rom.
     */
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
    /**
     * The user's play status: `incomplete`, `finished`, `completed_100`, `retired` or `never_playing`.
     */
    status: (RomUserStatus | null);
    /**
     * The media keys pinned on the overview, in order. Null means the default selection.
     */
    pinned_media: (Array<string> | null);
};

