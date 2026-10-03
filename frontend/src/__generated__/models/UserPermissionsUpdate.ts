/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { OverrideSchemaIO } from './OverrideSchemaIO';
export type UserPermissionsUpdate = {
    permission_group_id?: (number | null);
    set_group?: boolean;
    overrides?: (Array<OverrideSchemaIO> | null);
    age_limit?: (number | null);
    hide_unrated_roms?: (boolean | null);
    set_age_settings?: boolean;
};

