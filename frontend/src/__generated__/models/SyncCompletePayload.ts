/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SyncPlaySessionEntry } from './SyncPlaySessionEntry';
export type SyncCompletePayload = {
    operations_completed?: number;
    operations_failed?: number;
    play_sessions?: (Array<SyncPlaySessionEntry> | null);
};

