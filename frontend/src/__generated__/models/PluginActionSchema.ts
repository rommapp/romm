/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * One thing a plugin adds to the UI, with its URL template unexpanded.
 */
export type PluginActionSchema = {
    id: string;
    label: string;
    icon?: (string | null);
    image?: (string | null);
    url: string;
    open?: 'new-tab' | 'same-tab';
    slot?: 'game.details' | 'game.play' | 'app.nav' | 'settings.page';
    platforms?: Array<string>;
    enabled_by?: (string | null);
};

