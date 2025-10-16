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
    queued_at: string;
    started_at: (string | null);
    ended_at: (string | null);
    result: (Record<string, any> | null);
    task_type: "scan";
    meta: (ScanTaskMeta | null);
};

