/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncOperationSchema } from './SyncOperationSchema';
export type SyncNegotiateResponse = {
    session_id: number;
    operations: Array<SyncOperationSchema>;
    total_upload: number;
    total_download: number;
    total_conflict: number;
    total_no_op: number;
};

