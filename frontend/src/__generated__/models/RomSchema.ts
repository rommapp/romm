/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RomFile } from './RomFile';
import type { RomIGDBMetadata } from './RomIGDBMetadata';
import type { RomMobyMetadata } from './RomMobyMetadata';

export type RomSchema = {
    id: number;
    igdb_id: (number | null);
    sgdb_id: (number | null);
    moby_id: (number | null);
    platform_id: number;
    platform_slug: string;
    platform_fs_slug: string;
    platform_name: string;
    platform_custom_name: (string | null);
    platform_display_name: string;
    file_name: string;
    file_name_no_tags: string;
    file_name_no_ext: string;
    file_extension: string;
    file_path: string;
    file_size_bytes: number;
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    first_release_date: (number | null);
    youtube_video_id: (string | null);
    alternative_names: Array<string>;
    genres: Array<string>;
    franchises: Array<string>;
    collections: Array<string>;
    companies: Array<string>;
    game_modes: Array<string>;
    age_ratings: Array<string>;
    igdb_metadata: (RomIGDBMetadata | null);
    moby_metadata: (RomMobyMetadata | null);
    path_cover_s: (string | null);
    path_cover_l: (string | null);
    has_cover: boolean;
    url_cover: (string | null);
    revision: (string | null);
    regions: Array<string>;
    languages: Array<string>;
    tags: Array<string>;
    multi: boolean;
    files: Array<RomFile>;
    crc_hash: (string | null);
    md5_hash: (string | null);
    sha1_hash: (string | null);
    full_path: string;
    created_at: string;
    updated_at: string;
    readonly sort_comparator: string;
};

