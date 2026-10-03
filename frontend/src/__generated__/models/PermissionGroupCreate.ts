/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GrantSchemaIO } from './GrantSchemaIO';
export type PermissionGroupCreate = {
    name: string;
    description?: string;
    is_default?: boolean;
    color?: (string | null);
    grants?: Array<GrantSchemaIO>;
    age_limit?: (number | null);
    hide_unrated_roms?: boolean;
    age_exempt_rom_ids?: Array<number>;
};

