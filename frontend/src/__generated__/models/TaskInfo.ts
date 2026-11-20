/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TaskType } from './TaskType';
export type TaskInfo = {
    name: string;
    type: TaskType;
    /**
     * Whether the task can be run manually.
     */
    manual_run: boolean;
    title: string;
    description: string;
    enabled: boolean;
    destructive: boolean;
    cron_string: string;
};

