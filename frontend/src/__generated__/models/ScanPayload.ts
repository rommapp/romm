/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MetadataSource } from './MetadataSource';
import type { ScanType } from './ScanType';
/**
 * What to scan, with the options the `scan` socket event takes.
 */
export type ScanPayload = {
    type?: ScanType;
    platforms?: Array<number>;
    platform_fs_slugs?: Array<string>;
    roms_ids?: Array<number>;
    apis?: (Array<MetadataSource> | null);
    launchbox_remote_enabled?: boolean;
};

