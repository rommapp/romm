/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
import type { ScanTaskMeta } from './ScanTaskMeta';
export type ScanTaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: JobStatus;
    created_at: (string | null);
    enqueued_at: (string | null);
    started_at: (string | null);
    ended_at: (string | null);
    task_type: string;
    meta: ScanTaskMeta;
};

