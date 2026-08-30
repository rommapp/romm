/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SaveTargetLayout } from './SaveTargetLayout';
/**
 * Binary identity a client extracted for a ROM that RomM cannot read itself.
 */
export type RomIdentityData = {
    /**
     * Platform-native identity, e.g. 0100ABCD12340000 or SLUS-20152.
     */
    title_id?: (string | null);
    /**
     * On-disk name the emulator gives this game's saves.
     */
    save_target?: (string | null);
    /**
     * How to apply save_target when locating saves on disk.
     */
    save_target_layout?: (SaveTargetLayout | null);
};

