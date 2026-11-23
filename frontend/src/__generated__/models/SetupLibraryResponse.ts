/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PlatformSchema } from './PlatformSchema';
import type { SetupExistingPlatform } from './SetupExistingPlatform';
export type SetupLibraryResponse = {
    library_ready: boolean;
    library_structure: string;
    existing_platforms: Array<SetupExistingPlatform>;
    supported_platforms: Array<PlatformSchema>;
};

