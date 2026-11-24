/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Where a searchable field gets its choices.
 *
 * The list is served by the plugin's own source, not by RomM: RomM only asks
 * it and shows what comes back.
 */
export type PluginOptionSourceSchema = {
    url: string;
    query?: Record<string, string>;
    items: string;
    value: string;
    label: string;
    limit?: number;
};

