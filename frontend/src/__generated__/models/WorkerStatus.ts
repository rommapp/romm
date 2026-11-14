/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkerStatus = {
    ok: boolean;
    latency_ms: number;
    error: ('timeout' | 'unreachable' | 'error' | 'no_workers' | 'behind' | 'ahead' | 'unreadable' | 'unwritable' | null);
    workers: number;
    queues: Record<string, number>;
};

