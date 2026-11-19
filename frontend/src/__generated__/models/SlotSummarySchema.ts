/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SaveSchema } from './SaveSchema';
export type SlotSummarySchema = {
    /**
     * The slot name. Null for saves without a slot.
     */
    slot: (string | null);
    /**
     * The number of saves in the slot.
     */
    count: number;
    /**
     * The newest save in the slot.
     */
    latest: SaveSchema;
};

