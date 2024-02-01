/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { SaveSchema } from './SaveSchema';
import type { ScreenshotSchema } from './ScreenshotSchema';
import type { StateSchema } from './StateSchema';

export type RomSchema = {
    id: number;
    igdb_id: (number | null);
    sgdb_id: (number | null);
    platform_id: number;
    platform_slug: string;
    platform_name: string;
    file_name: string;
    file_name_no_tags: string;
    file_name_no_ext: string;
    file_extension: string;
    file_path: string;
    file_size_bytes: number;
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    total_rating: (string | null);
    genres: Array<string>;
    sort_comparator: string;
    path_cover_s: (string | null);
    path_cover_l: (string | null);
    has_cover: boolean;
    url_cover: (string | null);
    revision: (string | null);
    regions: Array<string>;
    languages: Array<string>;
    tags: Array<string>;
    multi: boolean;
    files: Array<string>;
    saves: Array<SaveSchema>;
    states: Array<StateSchema>;
    screenshots: Array<ScreenshotSchema>;
    url_screenshots: Array<string>;
    merged_screenshots: Array<string>;
    full_path: string;
    download_path: string;
};

