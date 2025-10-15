/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TaskType } from './TaskType';
export type TaskInfo = {
    name: string;
    manual_run: boolean;
    title: string;
    description: string;
    enabled: boolean;
    cron_string: string;
    task_type: TaskType;
};

