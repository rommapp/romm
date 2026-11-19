/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SlotSummarySchema } from './SlotSummarySchema';
export type SaveSummarySchema = {
    /**
     * The number of saves for the rom.
     */
    total_count: number;
    /**
     * A summary of each slot.
     */
    slots: Array<SlotSummarySchema>;
};

