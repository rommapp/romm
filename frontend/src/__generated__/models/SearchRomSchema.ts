/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { IGDBMetadata } from './IGDBMetadata';

export type SearchRomSchema = {
    igdb_id: (number | null);
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    url_cover: string;
    url_screenshots: Array<string>;
    metadata: (IGDBMetadata | null);
};

