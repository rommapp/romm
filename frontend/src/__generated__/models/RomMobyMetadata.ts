/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MobyMetadataPlatform } from './MobyMetadataPlatform';
import type { ScanClaims } from './ScanClaims';
export type RomMobyMetadata = {
    moby_score?: (string | null);
    genres?: Array<string>;
    alternate_titles?: Array<string>;
    platforms?: Array<MobyMetadataPlatform>;
    scan_claims?: ScanClaims;
};

