/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GenericTaskMeta } from './GenericTaskMeta';
import type { JobStatus } from './JobStatus';
export type GenericTaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: JobStatus;
    queued_at: string;
    started_at: (string | null);
    ended_at: (string | null);
    task_type: "generic";
    meta: (GenericTaskMeta | null);
};

