/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MissingFirmwareCleanupStats } from './MissingFirmwareCleanupStats';
import type { MissingRomsCleanupStats } from './MissingRomsCleanupStats';
import type { OrphanedResourcesCleanupStats } from './OrphanedResourcesCleanupStats';
export type CleanupTaskMeta = {
    cleanup_stats: (OrphanedResourcesCleanupStats | MissingRomsCleanupStats | MissingFirmwareCleanupStats | null);
};

