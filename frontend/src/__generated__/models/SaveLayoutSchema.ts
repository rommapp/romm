/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SaveLayoutOptionSchema } from './SaveLayoutOptionSchema';
/**
 * One of sigil's save layouts: `id` is what the content route takes as `core`.
 */
export type SaveLayoutSchema = {
    id: string;
    /**
     * Sigil's platform slug, "" for any platform
     */
    platform: string;
    options: Array<SaveLayoutOptionSchema>;
    /**
     * The option that picks a shared file by the disc's region, or ""
     */
    region_option: string;
    /**
     * An account save needs a user profile
     */
    profiles: boolean;
    /**
     * Restore names a new file only once one of the game's files is there
     */
    needs_existing: boolean;
};

