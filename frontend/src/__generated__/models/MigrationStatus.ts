/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type MigrationStatus = {
    ok: boolean;
    latency_ms: number;
    error: ('timeout' | 'unreachable' | 'error' | 'no_workers' | 'behind' | 'ahead' | 'unreadable' | 'unwritable' | null);
    current: (string | null);
    head: (string | null);
};

