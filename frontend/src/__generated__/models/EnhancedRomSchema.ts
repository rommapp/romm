/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RomSchema } from './RomSchema';

export type EnhancedRomSchema = {
    id: number;
    igdb_id: (number | null);
    sgdb_id: (number | null);
    platform_slug: string;
    platform_name: string;
    file_name: string;
    file_name_no_tags: string;
    file_extension: string;
    file_path: string;
    file_size: number;
    file_size_units: string;
    file_size_bytes: number;
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    sort_comparator: string;
    path_cover_s: string;
    path_cover_l: string;
    has_cover: boolean;
    url_cover: string;
    revision: (string | null);
    regions: Array<string>;
    languages: Array<string>;
    tags: Array<string>;
    multi: boolean;
    files: Array<string>;
    url_screenshots: Array<string>;
    path_screenshots: Array<string>;
    full_path: string;
    download_path: string;
    sibling_roms: Array<RomSchema>;
};

