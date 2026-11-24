/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A panel a plugin fills by asking its own server for data.
 *
 * The UI needs to know that a panel exists and where it belongs; what it
 * fetches, and how, stays on the server, so a manifest's request cannot be
 * read back out of the plugin list.
 */
export type PluginFactSummarySchema = {
    id: string;
    label: string;
    slot?: 'game.details' | 'game.play' | 'app.nav' | 'settings.page';
};

