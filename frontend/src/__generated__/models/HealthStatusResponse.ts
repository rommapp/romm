/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DatabaseStatus } from './DatabaseStatus';
import type { LibraryCheck } from './LibraryCheck';
import type { MigrationStatus } from './MigrationStatus';
import type { ResourcesCheck } from './ResourcesCheck';
import type { ValkeyStatus } from './ValkeyStatus';
import type { WorkerStatus } from './WorkerStatus';
export type HealthStatusResponse = {
    database: DatabaseStatus;
    valkey: ValkeyStatus;
    worker: WorkerStatus;
    migration: MigrationStatus;
    library: LibraryCheck;
    resources: ResourcesCheck;
};

