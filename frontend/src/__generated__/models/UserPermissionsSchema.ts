/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { HiddenEntitySchema } from './HiddenEntitySchema';
import type { OverrideSchemaIO } from './OverrideSchemaIO';
/**
 * Admin view of one user's permission assignment.
 */
export type UserPermissionsSchema = {
    user_id: number;
    permission_group_id: (number | null);
    overrides: Array<OverrideSchemaIO>;
    hidden: Array<HiddenEntitySchema>;
    age_limit?: (number | null);
    hide_unrated_roms?: (boolean | null);
    age_exempt_rom_ids?: Array<number>;
};

