/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SessionTerminationSchema } from './SessionTerminationSchema';
export type SessionStatusSchema = {
    status: 'active' | 'ended';
    platform: string;
    extraction_phase?: (string | null);
    host?: (string | null);
    container?: (string | null);
    termination?: (SessionTerminationSchema | null);
};

