/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GrantSchemaIO } from './GrantSchemaIO';
export type PermissionGroupCreate = {
    name: string;
    description?: string;
    is_default?: boolean;
    grants?: Array<GrantSchemaIO>;
};

