/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { JobStatus } from './JobStatus';
import type { WatcherTaskMeta } from './WatcherTaskMeta';
export type WatcherTaskStatusResponse = {
    task_name: string;
    task_id: string;
    status: JobStatus;
    queued_at: string;
    started_at: (string | null);
    ended_at: (string | null);
    task_type: "watcher";
    meta: WatcherTaskMeta;
};

