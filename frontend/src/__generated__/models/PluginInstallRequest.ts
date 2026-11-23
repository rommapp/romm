/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Where a new plugin comes from: a URL to fetch, or a manifest to store.
 */
export type PluginInstallRequest = {
    url?: (string | null);
    /**
     * A plugin.json body
     */
    manifest?: (Record<string, any> | null);
};

