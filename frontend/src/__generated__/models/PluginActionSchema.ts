/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One button a plugin adds to a game, with its URL template unexpanded.
 */
export type PluginActionSchema = {
    id: string;
    label: string;
    icon?: (string | null);
    url: string;
    open?: 'new-tab' | 'same-tab';
};

