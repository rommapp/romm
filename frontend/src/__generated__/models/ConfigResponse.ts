/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EjsControls } from './EjsControls';
export type ConfigResponse = {
    CONFIG_FILE_MOUNTED: boolean;
    CONFIG_FILE_WRITABLE: boolean;
    EXCLUDED_PLATFORMS: Array<string>;
    EXCLUDED_SINGLE_EXT: Array<string>;
    EXCLUDED_SINGLE_FILES: Array<string>;
    EXCLUDED_MULTI_FILES: Array<string>;
    EXCLUDED_MULTI_PARTS_EXT: Array<string>;
    EXCLUDED_MULTI_PARTS_FILES: Array<string>;
    PLATFORMS_BINDING: Record<string, string>;
    PLATFORMS_VERSIONS: Record<string, string>;
    EJS_DEBUG: boolean;
    EJS_CACHE_LIMIT: (number | null);
    EJS_SETTINGS: Record<string, Record<string, string>>;
    EJS_CONTROLS: Record<string, EjsControls>;
    SCAN_METADATA_PRIORITY: Array<string>;
    SCAN_ARTWORK_PRIORITY: Array<string>;
    SCAN_REGION_PRIORITY: Array<string>;
    SCAN_LANGUAGE_PRIORITY: Array<string>;
};

