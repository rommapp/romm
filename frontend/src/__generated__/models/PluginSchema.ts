/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PluginActionSchema } from "./PluginActionSchema";
import type { PluginSettingSchema } from "./PluginSettingSchema";
/**
 * A plugin manifest, as the UI reads it.
 */
export type PluginSchema = {
  id: string;
  name: string;
  version: string;
  description?: string | null;
  author?: string | null;
  homepage?: string | null;
  actions?: Array<PluginActionSchema>;
  settings?: Array<PluginSettingSchema>;
};
