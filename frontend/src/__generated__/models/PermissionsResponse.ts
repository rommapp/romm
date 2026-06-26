/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { GrantSchema } from './GrantSchema';
import type { HiddenEntitiesSchema } from './HiddenEntitiesSchema';
export type PermissionsResponse = {
    is_admin: boolean;
    grants: Array<GrantSchema>;
    hidden: HiddenEntitiesSchema;
};

