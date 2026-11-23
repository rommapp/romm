/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MetadataCoverageItem } from './MetadataCoverageItem';
import type { RegionBreakdownItem } from './RegionBreakdownItem';
export type StatsReturn = {
    PLATFORMS?: number;
    ROMS?: number;
    SAVES?: number;
    STATES?: number;
    SCREENSHOTS?: number;
    TOTAL_FILESIZE_BYTES?: number;
    METADATA_COVERAGE?: Record<string, Array<MetadataCoverageItem>>;
    REGION_BREAKDOWN?: Record<string, Array<RegionBreakdownItem>>;
};

