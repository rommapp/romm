/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SlotCapabilitiesSchema } from './SlotCapabilitiesSchema';
/**
 * One platform the fleet can stream, as the play screen needs it.
 */
export type StreamingContainerSchema = {
    platform: string;
    host: string;
    label: string;
    capabilities: SlotCapabilitiesSchema;
    emulator: string;
    supports_memory_cards: boolean;
};

