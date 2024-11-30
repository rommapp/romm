/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { FirmwareSchema } from './FirmwareSchema';

export type PlatformSchema = {
    id: number;
    slug: string;
    fs_slug: string;
    name: string;
    rom_count: number;
    igdb_id?: (number | null);
    sgdb_id?: (number | null);
    moby_id?: (number | null);
    category?: (string | null);
    generation?: (number | null);
    family_name?: (string | null);
    family_slug?: (string | null);
    url?: (string | null);
    url_logo?: (string | null);
    logo_path?: (string | null);
    firmware?: Array<FirmwareSchema>;
    created_at: string;
    updated_at: string;
};

