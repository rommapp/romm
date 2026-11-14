/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LibraryCheck } from './LibraryCheck';
import type { ReadyCheck } from './ReadyCheck';
import type { ResourcesCheck } from './ResourcesCheck';
export type HealthReadyResponse = {
    database: ReadyCheck;
    valkey: ReadyCheck;
    worker: ReadyCheck;
    migration: ReadyCheck;
    library: LibraryCheck;
    resources: ResourcesCheck;
};

