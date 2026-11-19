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
    /**
     * The host of the container.
     */
    host: string;
    /**
     * The display name of the container.
     */
    label: string;
    capabilities: SlotCapabilitiesSchema;
    /**
     * The emulator the container runs.
     */
    emulator: string;
    /**
     * Whether the container supports memory cards.
     */
    supports_memory_cards: boolean;
    /**
     * Whether the container supports the save picker.
     */
    supports_save_picker: boolean;
    /**
     * Whether the container supports live states.
     */
    supports_live_states: boolean;
    /**
     * The kinds of picks from other emulators the broker can import. Empty when it declares none or cannot be asked.
     */
    import_kinds: Array<'save' | 'state'>;
};

