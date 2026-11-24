/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PluginOptionSchema } from './PluginOptionSchema';
/**
 * The choices a search found.
 *
 * An error is said in `note` and comes with an empty list: a source that is
 * down is not a reason to close the form.
 */
export type PluginOptionsSchema = {
    options?: Array<PluginOptionSchema>;
    note?: (string | null);
};

