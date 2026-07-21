/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MetadataMediaType } from './MetadataMediaType';
/**
 * Full replacement of the scan.* config section.
 *
 * The three artwork override lists (cover/screenshot/manual) are optional:
 * a null value clears the override so that field falls back to
 * `artwork_priority`.
 */
export type ScanSettingsPayload = {
    metadata_priority: Array<string>;
    artwork_priority: Array<string>;
    cover_priority?: (Array<string> | null);
    screenshot_priority?: (Array<string> | null);
    manual_priority?: (Array<string> | null);
    region_priority: Array<string>;
    language_priority: Array<string>;
    media: Array<MetadataMediaType>;
    gamelist_export: boolean;
    gamelist_thumbnail: MetadataMediaType;
    gamelist_image: MetadataMediaType;
    pegasus_export: boolean;
};

