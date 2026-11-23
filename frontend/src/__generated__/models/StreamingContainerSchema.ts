/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SlotCapabilitiesSchema } from './SlotCapabilitiesSchema';
/**
 * One platform the fleet can stream, as the play screen needs it.
 */
export type StreamingContainerSchema = {
    /**
     * The slug of the platform the container serves.
     */
    platform: string;
    host: string;
    /**
     * The display name of the container.
     */
    label: string;
    capabilities: SlotCapabilitiesSchema;
    emulator: string;
    supports_memory_cards: boolean;
    supports_save_picker: boolean;
    supports_live_states: boolean;
    /**
     * The kinds of files from other emulators, saves or states, that the broker can import. Empty when the broker declares none or does not answer.
     */
    import_kinds: Array<'save' | 'state'>;
};

