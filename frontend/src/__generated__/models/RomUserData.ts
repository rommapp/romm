/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomUserStatus } from './RomUserStatus';
export type RomUserData = {
    /**
     * Whether this rom is the main version of its game.
     */
    is_main_sibling?: (boolean | null);
    /**
     * Whether this rom is in the backlog.
     */
    backlogged?: (boolean | null);
    /**
     * Whether this rom is currently being played.
     */
    now_playing?: (boolean | null);
    /**
     * Whether this rom is hidden.
     */
    hidden?: (boolean | null);
    /**
     * User rating for this rom (0-10).
     */
    rating?: (number | null);
    /**
     * User difficulty rating for this rom (0-10).
     */
    difficulty?: (number | null);
    /**
     * User completion percentage for this rom (0-100).
     */
    completion?: (number | null);
    /**
     * User play status for this rom.
     */
    status?: (RomUserStatus | null);
    /**
     * The media keys to show on the overview, in order. Null restores the default selection.
     */
    pinned_media?: (Array<string> | null);
};

