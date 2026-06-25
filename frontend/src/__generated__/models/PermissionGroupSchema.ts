/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GrantSchemaIO } from './GrantSchemaIO';
import type { HiddenEntitySchema } from './HiddenEntitySchema';
export type PermissionGroupSchema = {
    id: number;
    name: string;
    description: string;
    is_default: boolean;
    is_system: boolean;
    color: (string | null);
    grants: Array<GrantSchemaIO>;
    member_count: number;
    hidden?: Array<HiddenEntitySchema>;
};

