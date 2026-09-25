/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { StreamingContainerSchema } from './StreamingContainerSchema';
export type StreamingConfigSchema = {
    enabled: boolean;
    containers: Array<StreamingContainerSchema>;
    emulator_labels: Record<string, string>;
};

