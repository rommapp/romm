/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { FirmwareSchema } from './FirmwareSchema';

export type PlatformSchema = {
    id: number;
    slug: string;
    fs_slug: string;
    igdb_id?: (number | null);
    sgdb_id?: (number | null);
    moby_id?: (number | null);
    name: string;
    logo_path?: (string | null);
    rom_count: number;
    firmware_files?: Array<FirmwareSchema>;
};
