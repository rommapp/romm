/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CleanupTaskMeta } from './CleanupTaskMeta';
import type { JobStatus } from './JobStatus';
export type CleanupTaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: JobStatus;
    queued_at: string;
    started_at: (string | null);
    ended_at: (string | null);
    result: (Record<string, any> | null);
    task_type: "cleanup";
    meta: (CleanupTaskMeta | null);
};

