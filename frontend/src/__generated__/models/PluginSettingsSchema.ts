/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A plugin's saved values, keyed by the manifest's setting keys.
 *
 * A value is whatever the field holds, which for a `groups` field is a list of
 * entries. Narrowing this to scalars would refuse the whole request before the
 * manifest got a look at it.
 */
export type PluginSettingsSchema = {
  values?: Record<string, any>;
};
