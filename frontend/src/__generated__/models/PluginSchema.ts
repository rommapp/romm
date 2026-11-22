/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PluginActionSchema } from './PluginActionSchema';
export type PluginSchema = {
    id: string;
    name: string;
    version: string;
    description?: (string | null);
    author?: (string | null);
    homepage?: (string | null);
    actions?: Array<PluginActionSchema>;
};
