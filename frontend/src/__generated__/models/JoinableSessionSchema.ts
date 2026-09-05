/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A session its host opened to other players, plus enough of the ROM to
 * draw a cover tile without a second request per session.
 */
export type JoinableSessionSchema = {
    container: string;
    label?: (string | null);
    platform?: (string | null);
    rom_id?: (number | null);
    rom_name?: (string | null);
    host_username?: (string | null);
    claimed_at?: (string | null);
    platform_id?: (number | null);
    platform_display_name?: (string | null);
    path_cover_small?: (string | null);
    path_cover_large?: (string | null);
    url_cover?: (string | null);
};

