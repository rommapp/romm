/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EjsControlsButton } from './EjsControlsButton';
export type ConfigResponse = {
    EXCLUDED_PLATFORMS: Array<string>;
    EXCLUDED_SINGLE_EXT: Array<string>;
    EXCLUDED_SINGLE_FILES: Array<string>;
    EXCLUDED_MULTI_FILES: Array<string>;
    EXCLUDED_MULTI_PARTS_EXT: Array<string>;
    EXCLUDED_MULTI_PARTS_FILES: Array<string>;
    PLATFORMS_BINDING: Record<string, string>;
    PLATFORMS_VERSIONS: Record<string, string>;
    EJS_DEBUG: boolean;
    EJS_OPTIONS: Record<string, Record<string, string>>;
    EJS_CONTROLS: Record<string, Record<string, Record<string, EjsControlsButton>>>;
};

