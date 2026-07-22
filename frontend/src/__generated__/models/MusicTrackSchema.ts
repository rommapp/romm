/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type MusicTrackSchema = {
    rom_file_id: number;
    rom_id: number;
    title?: (string | null);
    artist?: (string | null);
    album?: (string | null);
    genre?: (string | null);
    year?: (number | null);
    track?: (number | null);
    disc?: (number | null);
    duration_seconds?: (number | null);
    has_embedded_cover?: boolean;
    md5_hash?: (string | null);
    is_favorite?: boolean;
    game_name?: (string | null);
    platform_id: number;
    platform_slug: string;
    platform_name: string;
    stream_url: string;
    cover_url?: (string | null);
};

