/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PluginOptionSourceSchema } from './PluginOptionSourceSchema';
import type { PluginSettingOptionSchema } from './PluginSettingOptionSchema';
/**
 * One field a plugin's settings form shows.
 */
export type PluginSettingSchema = {
    key: string;
    label: string;
    type?: 'text' | 'url' | 'number' | 'boolean' | 'select' | 'password' | 'search' | 'groups';
    default?: (string | number | boolean | null);
    help?: (string | null);
    placeholder?: (string | null);
    options?: Array<PluginSettingOptionSchema>;
    min?: (number | null);
    max?: (number | null);
    required?: boolean;
    source?: (PluginOptionSourceSchema | null);
    fields?: Array<PluginSettingSchema>;
    max_items?: number;
};

