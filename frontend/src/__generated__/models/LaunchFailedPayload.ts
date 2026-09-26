/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ImportRefusalSchema } from './ImportRefusalSchema';
/**
 * `streaming:launch-failed`. The claim is already released.
 */
export type LaunchFailedPayload = {
    platform: string;
    container: string;
    claimed_at: string;
    detail: string;
    refusals?: (Array<ImportRefusalSchema> | null);
    refusals_truncated?: number;
};

