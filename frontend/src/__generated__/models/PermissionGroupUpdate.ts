/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GrantSchemaIO } from './GrantSchemaIO';
export type PermissionGroupUpdate = {
    name?: (string | null);
    description?: (string | null);
    is_default?: (boolean | null);
    color?: (string | null);
    grants?: (Array<GrantSchemaIO> | null);
    age_limit?: (number | null);
    hide_unrated_roms?: boolean;
    set_age_settings?: boolean;
    age_exempt_rom_ids?: (Array<number> | null);
};

