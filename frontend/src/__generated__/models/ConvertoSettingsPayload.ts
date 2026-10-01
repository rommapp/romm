/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * The converto.* settings editable at runtime; `cache_ttl_hours` stays config.yml-only.
 */
export type ConvertoSettingsPayload = {
    download_conversion_enabled: boolean;
    scan_metadata: boolean;
    cache_max_size_gb: number;
    platform_formats: Record<string, string>;
};

