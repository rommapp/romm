/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
import type { ScanTaskMeta } from './ScanTaskMeta';
export type ScanTaskStatusResponse = {
    /**
     * The key of the task in the catalog. Null for scans that a client or the file watcher started outside the catalog.
     */
    task_key: (string | null);
    task_name: string;
    /**
     * The job ID, which `GET /tasks/{task_id}` takes.
     */
    task_id: string;
    status: JobStatus;
    created_at: (string | null);
    enqueued_at: (string | null);
    started_at: (string | null);
    ended_at: (string | null);
    task_type: string;
    meta: ScanTaskMeta;
};

